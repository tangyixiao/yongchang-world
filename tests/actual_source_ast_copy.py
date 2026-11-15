"""Fast, isolated copies of parsed source in the JHG/TIB test interpreters.

Parser blocks are lists of (str, str, str-or-list) tuples. Only a terminal
tuple of three exact strings is immutable; every mutable block is copied.
The caller's deepcopy memo preserves aliases into ordinary runtime state.
"""
import copy


_MISSING = object()
_ATOMIC_PROBE = 'actual-source-copy-atomic-probe'
# Python 3.12 consults memo before atomics; 3.14 returns atomics first. Keep
# the original world-copy path on runtimes with the older memo semantics.
_ATOMICS_IGNORE_MEMO = copy.deepcopy(
    _ATOMIC_PROBE, {id(_ATOMIC_PROBE): None}) is _ATOMIC_PROBE
_REGISTRIES = ('effects', 'triggers', 'trigger_defs', 'journal_defs',
               'event_defs', 'inline_registries', 'named_values',
               'modifier_defs', 'on_actions')


def copy_source_ast(value, memo):
    """Copy current parser containers; retain deepcopy for all other shapes."""
    kind = type(value)
    if not _ATOMICS_IGNORE_MEMO:
        return copy.deepcopy(value, memo)
    if kind is str:
        return value
    if kind is not list and kind is not dict:
        return copy.deepcopy(value, memo)
    identity = id(value)
    found = memo.get(identity, _MISSING)
    if found is not _MISSING:
        return found
    if kind is dict:
        result = {}
        memo[identity] = result
        for key, child in value.items():
            result[key if type(key) is str else copy.deepcopy(key, memo)] = copy_source_ast(child, memo)
        return result
    result = []
    memo[identity] = result
    for node in value:
        if (type(node) is tuple and len(node) == 3
                and type(node[0]) is str and type(node[1]) is str):
            child = node[2]
            if type(child) is str:
                result.append(memo.get(id(node), node))
                continue
            if type(child) is list:
                node_id = id(node)
                found = memo.get(node_id, _MISSING)
                if found is _MISSING:
                    child_copy = copy_source_ast(child, memo)
                    # As in deepcopy's tuple protocol, recursion may already
                    # have completed this tuple through a list/tuple cycle.
                    found = memo.get(node_id, _MISSING)
                    if found is _MISSING:
                        found = (node[0], node[1], child_copy)
                        memo[node_id] = found
                result.append(found)
                continue
        result.append(copy.deepcopy(node, memo))
    return result


def seed_source_ast_memo(world, memo):
    """Copy registries first, including the JHG typed partner's definitions.

No snapshot is cached: edits and newly inserted definitions are read on every
copy. Runtime objects, observers, dispatch lists and callbacks continue through
the existing world-copy protocol with this same memo.
"""
    if not _ATOMICS_IGNORE_MEMO:
        return
    owners = (world, getattr(world, 'escort_partner_world', None))
    for owner in owners:
        if owner is None:
            continue
        for name in _REGISTRIES:
            if name in owner.__dict__:
                copy_source_ast(owner.__dict__[name], memo)
