"""Strict source-span parser and generated adapters for inline Clausewitz senders."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any

_TOKEN = re.compile(r'[A-Za-z_][A-Za-z0-9_:.]*|-?[0-9]+(?:\.[0-9]+)?|\?=|>=|<=|!=|=|<|>|\{|\}|"(?:\\.|[^"\\])*"')


@dataclass(frozen=True)
class Node:
    key: str
    op: str
    value: str | tuple["Node", ...]
    start: int
    end: int
    value_start: int
    value_end: int


def _tokens(text: str) -> list[tuple[str, int, int]]:
    """Tokenize Clausewitz structure while retaining exact source offsets."""
    out: list[tuple[str, int, int]] = []
    i = 0
    while i < len(text):
        if text[i].isspace():
            i += 1; continue
        if text.startswith("#", i):
            end = text.find("\n", i)
            i = len(text) if end < 0 else end + 1
            continue
        m = _TOKEN.match(text, i)
        if not m:
            raise ValueError(f"unsupported Clausewitz character at offset {i}: {text[i]!r}")
        out.append((m.group(), m.start(), m.end()))
        i = m.end()
    return out


def parse_block(text: str) -> tuple[Node, ...]:
    """Parse a complete `{ ... }` script block; reject malformed or unknown syntax."""
    tokens = _tokens(text)
    if not tokens or tokens[0][0] != "{" or tokens[-1][0] != "}":
        raise ValueError("script must be one complete Clausewitz block")
    idx = 0

    def sequence(close: bool) -> tuple[Node, ...]:
        nonlocal idx
        result: list[Node] = []
        while idx < len(tokens) and tokens[idx][0] != "}":
            if tokens[idx][0] in ("{", "}", "=", "?=", ">=", "<=", "!=", "<", ">"):
                raise ValueError(f"unexpected structural token {tokens[idx][0]!r}")
            key, start, _ = tokens[idx]; idx += 1
            if idx >= len(tokens) or tokens[idx][0] not in ("=", "?=", ">=", "<=", "!=", "<", ">"):
                raise ValueError(f"expected an operator after {key}")
            op = tokens[idx][0]
            idx += 1
            if idx >= len(tokens) or tokens[idx][0] in ("}", "=", "?=", ">=", "<=", "!=", "<", ">"): raise ValueError(f"missing or invalid value for {key}")
            if tokens[idx][0] == "{":
                open_start = tokens[idx][1]; idx += 1
                children = sequence(True)
                if idx >= len(tokens) or tokens[idx][0] != "}":
                    raise ValueError(f"unclosed block for {key}")
                close_end = tokens[idx][2]; idx += 1
                result.append(Node(key, op, children, start, close_end, open_start, close_end))
            else:
                value, vstart, vend = tokens[idx]; idx += 1
                result.append(Node(key, op, value, start, vend, vstart, vend))
        if close and idx >= len(tokens): raise ValueError("unclosed Clausewitz block")
        return tuple(result)

    if tokens[0][0] != "{": raise ValueError("missing opening brace")
    idx = 1
    nodes = sequence(True)
    if idx >= len(tokens) or tokens[idx][0] != "}": raise ValueError("missing closing brace")
    idx += 1
    if idx != len(tokens): raise ValueError("trailing tokens after Clausewitz block")
    return nodes


def render_node(node: Node, source: str) -> str:
    return source[node.start:node.end]


def _mgl_render_nodes(nodes: tuple[Node, ...]) -> str:
    """Render parsed MGL guard nodes without carrying comments into joins."""
    rendered: list[str] = []
    for node in nodes:
        if isinstance(node.value, tuple):
            value = "{ " + _mgl_render_nodes(node.value) + " }"
        else:
            value = node.value
        rendered.append(f"{node.key} {node.op} {value}")
    return " ".join(rendered)


def _mgl_inner_text(block: str) -> str:
    """Canonicalize an MGL source block through the strict AST parser."""
    value = block.strip()
    nodes = parse_block(value)
    return _mgl_render_nodes(nodes)


def _mgl_exact_typed_equal(actual: Any, expected: Any) -> bool:
    """Compare JSON-like MGL metadata without Python bool/int/float coercion."""
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(
            _mgl_exact_typed_equal(actual[key], value) for key, value in expected.items()
        )
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(
            _mgl_exact_typed_equal(left, right) for left, right in zip(actual, expected)
        )
    return actual == expected


def children(node: Node) -> tuple[Node, ...]:
    if not isinstance(node.value, tuple): raise ValueError(f"{node.key} is not a block")
    return node.value


def block_digest(node: Node, source: str) -> str:
    return hashlib.sha256(render_node(node, source).encode("utf-8")).hexdigest()


def direct_values(nodes: tuple[Node, ...], key: str) -> list[Node]:
    return [node for node in nodes if node.key == key]


def trigger_event_ids(nodes: tuple[Node, ...]) -> list[str]:
    found: list[str] = []
    def visit(items: tuple[Node, ...]) -> None:
        for node in items:
            if node.key == "trigger_event":
                values = direct_values(children(node), "id")
                if len(values) != 1 or not isinstance(values[0].value, str):
                    raise ValueError("trigger_event must contain exactly one literal id")
                found.append(values[0].value)
            elif isinstance(node.value, tuple): visit(node.value)
    visit(nodes)
    return found


def replace_node_span(source: str, node: Node, replacement: str) -> str:
    if not isinstance(replacement, str) or not replacement.strip(): raise ValueError("replacement must be nonempty")
    return source[:node.start] + replacement + source[node.end:]


def source_binding(journal_id: str, pulse: str) -> dict[str, Any]:
    """Return ordered sender branch spans without interpreting business predicates."""
    top = parse_block(pulse)
    monthly = direct_values(top, "on_monthly_pulse")
    if len(monthly) != 1: raise ValueError(f"{journal_id}: expected one on_monthly_pulse block")
    pulses = direct_values(children(monthly[0]), "effect")
    if len(pulses) != 1: raise ValueError(f"{journal_id}: monthly pulse must have one effect block")
    nodes = children(pulses[0])
    out = []
    covered_events: set[tuple[int, int]] = set()
    seen_sender_digests: set[str] = set()
    previous_was_branch = False
    for ordinal, node in enumerate(nodes):
        is_branch = node.key in {"if", "else_if"}
        if node.key == "else_if" and not previous_was_branch:
            raise ValueError(f"{journal_id}: orphan else_if in monthly effect")
        previous_was_branch = is_branch
        nested_ids = trigger_event_ids((node,)) if is_branch else trigger_event_ids((node,))
        if not is_branch:
            if nested_ids:
                raise ValueError(f"{journal_id}: trigger_event is outside a supported direct sender branch")
            continue
        direct_triggers = direct_values(children(node), "trigger_event")
        ids = trigger_event_ids((node,))
        if not ids:
            continue
        if len(direct_triggers) != 1 or len(ids) != 1:
            raise ValueError(f"{journal_id}: sender must contain exactly one direct trigger_event and no nested trigger_event")
        covered_events.add((direct_triggers[0].start, direct_triggers[0].end))
        if len(ids) != 1: raise ValueError(f"{journal_id}: one sender branch must trigger exactly one event")
        limits = direct_values(children(node), "limit")
        if len(limits) != 1: raise ValueError(f"{journal_id}: sender branch must contain exactly one limit")
        limit = limits[0]
        children(limit)
        digest = block_digest(node, pulse)
        if digest in seen_sender_digests:
            raise ValueError(f"{journal_id}: duplicate identical sender branch")
        seen_sender_digests.add(digest)
        out.append({"branch_index": len(out), "statement_ordinal": ordinal, "event": ids[0], "start": node.start, "end": node.end,
                    "sha256": digest, "limit_start": limit.start,
                    "limit_end": limit.end, "limit_sha256": block_digest(limit, pulse),
                    "limit_source": render_node(limit, pulse)})
    # The recursive scan catches nested trigger_event nodes in unrelated scopes, while
    # the source branches above prove each accepted sender is an immediate child.
    def all_trigger_spans(items: tuple[Node, ...]):
        for item in items:
            if item.key == "trigger_event":
                yield item.start, item.end
            elif isinstance(item.value, tuple):
                yield from all_trigger_spans(item.value)
    actual_event_spans = list(all_trigger_spans(nodes))
    if len(actual_event_spans) != len(set(actual_event_spans)) or set(actual_event_spans) != covered_events:
        raise ValueError(f"{journal_id}: trigger_event exists outside exactly one supported sender branch")
    return {"journal": journal_id, "branches": out}


def inject_limit_guard(source: str, branch: dict[str, Any], guard: str) -> str:
    """Append one adapter guard to the exact authored sender branch limit block."""
    if not isinstance(guard, str) or not guard.strip(): raise ValueError("guard must be nonempty")
    parsed = source_binding("<source>", source)
    matches = [item for item in parsed["branches"] if item["start"] == branch.get("start") and item["end"] == branch.get("end")]
    if len(matches) != 1 or matches[0]["sha256"] != branch.get("sha256"):
        raise ValueError("sender branch source span/hash mismatch")
    limit_start, limit_end = matches[0]["limit_start"], matches[0]["limit_end"]
    if source[limit_start:limit_end] != branch.get("limit_source"):
        raise ValueError("sender limit source span mismatch")
    close = limit_end - 1
    prefix = source[:close]
    compact = prefix.rstrip()
    trailing = prefix[len(compact):]
    return compact + " " + guard + trailing + source[close:]

def _walk(nodes: tuple[Node, ...]):
    for node in nodes:
        yield node
        if isinstance(node.value, tuple): yield from _walk(node.value)


def queue_candidates(branch_source: str) -> list[dict[str, Any]]:
    """Derive queue class/value predicates only from actual source condition nodes."""
    if not isinstance(branch_source, str) or not branch_source.strip(): raise ValueError("sender branch source must be nonempty")
    nodes = parse_block("{ " + branch_source + " }")
    limits = direct_values(nodes, "limit")
    if len(limits) != 1: raise ValueError("sender branch must contain one limit")
    found: dict[tuple[str, str], dict[str, Any]] = {}
    def positive_nodes(items: tuple[Node, ...]):
        for item in items:
            if item.key == "NOT" and isinstance(item.value, tuple):
                # A queue name under NOT is an exclusion, never a dispatch candidate.
                continue
            yield item
            if isinstance(item.value, tuple):
                yield from positive_nodes(item.value)
    for node in positive_nodes(children(limits[0])):
        if not isinstance(node.value, str): continue
        variable = None; mode = None; value = None
        if node.key == "has_variable" and node.value.startswith(("ywc_dmg_", "ywc_nqg_")):
            if node.value.endswith("_notice") or node.value.endswith("_emergency_notice"):
                variable, mode = node.value, "presence"
            elif node.value.endswith(("_notice12_pending", "_notice36_pending", "_remedy_final_pending")):
                variable, mode = node.value, "presence"
        elif node.key.startswith(("var:ywc_dmg_", "var:ywc_nqg_")) and node.op == "=" and node.value.isdigit():
            variable, mode, value = node.key.removeprefix("var:"), "exact", int(node.value)
        if not variable: continue
        if variable.endswith(("_blocked_12_notice", "_emergency_notice", "_state_lost_notice", "_notice12_pending")):
            kind = "notice12"
        elif variable.endswith("_blocked_36_notice"):
            kind = "notice36"
        elif variable.endswith("_notice36_pending"):
            kind = "notice36"
        elif variable.endswith("_remedy_final_pending"):
            kind = "remedy_final"
        elif variable.endswith(("_pending_event", "_pending")) and not variable.endswith(("_notice12_pending", "_notice36_pending", "_remedy_final_pending")):
            kind = "normal"
        else:
            continue
        identity = (variable, kind)
        item = {"queue": variable, "mode": mode, "kind": kind}
        if mode == "exact": item["value"] = value
        found[identity] = item
    return sorted(found.values(), key=lambda item: (item["kind"], item["queue"], item.get("value", -1)))


def _kor_queue_candidates(branch_source: str) -> list[dict[str, Any]]:
    """Collect only positive KOR queue predicates, retaining exact source semantics."""
    nodes = parse_block("{ " + branch_source + " }")
    if len(nodes) != 1 or nodes[0].key not in {"if", "else_if"}:
        raise ValueError("KOR source site must be one if/else_if branch")
    limits = direct_values(children(nodes[0]), "limit")
    if len(limits) != 1:
        raise ValueError("KOR sender branch must have exactly one limit")
    found: dict[tuple[str, str, int | None], dict[str, Any]] = {}

    def visit(items: tuple[Node, ...], excluded: bool = False) -> None:
        for node in items:
            negative = excluded or node.key == "NOT"
            if isinstance(node.value, tuple):
                visit(node.value, negative)
                continue
            if excluded or not isinstance(node.value, str):
                continue
            variable: str | None = None
            mode: str | None = None
            value: int | None = None
            if node.key.startswith(("var:ywc_kor_", "var:ywc_nqg_", "var:ywc_shu_")) and node.op == "=" and node.value.isdigit():
                raw = node.key.removeprefix("var:")
                if raw.endswith(("_pending_event", "_notice_event", "_pending")):
                    variable, mode, value = raw, "exact", int(node.value)
            elif node.key == "has_variable" and node.op == "=" and node.value.startswith(("ywc_kor_", "ywc_nqg_", "ywc_shu_")):
                raw = node.value
                if raw.endswith(("_pending_event", "_notice_event", "_pending")):
                    variable, mode = raw, "presence"
            if not variable:
                continue
            if variable.endswith(("_notice12_pending", "_blocked_12_notice", "_emergency_notice", "_state_lost_notice")):
                kind = "notice12"
            elif variable.endswith(("_notice36_pending", "_blocked_36_notice")):
                kind = "notice36"
            elif variable.endswith("_remedy_final_pending"):
                kind = "remedy_final"
            elif variable.endswith(("_notice_event",)):
                kind = "notice"
            else:
                kind = "normal_queued_event" if variable.startswith("ywc_nqg_") else "normal"
            identity = (variable, mode, value)
            candidate = {"queue": variable, "kind": kind, "mode": mode}
            if mode == "exact":
                candidate["value"] = value
            found[identity] = candidate

    visit(children(limits[0]))
    kind_order = {"remedy_final": 0, "notice12": 1, "notice36": 2, "normal_queued_event": 3, "normal": 0, "notice": 1}
    return sorted(found.values(), key=lambda item: (kind_order.get(item["kind"], 9), item["queue"], item.get("value", -1)))


def _kor_queue_exclusions(branch_source: str) -> list[dict[str, Any]]:
    nodes = parse_block("{ " + branch_source + " }")
    if len(nodes) != 1 or nodes[0].key not in {"if", "else_if"}:
        raise ValueError("KOR source site must be one if/else_if branch")
    limits = direct_values(children(nodes[0]), "limit")
    if len(limits) != 1:
        raise ValueError("KOR sender branch must have exactly one limit")
    exclusions: list[dict[str, Any]] = []

    def visit(items: tuple[Node, ...], negative: bool = False) -> None:
        for node in items:
            under_not = negative or node.key == "NOT"
            if isinstance(node.value, tuple):
                visit(node.value, under_not)
                continue
            if not under_not or not isinstance(node.value, str):
                continue
            if node.key.startswith(("var:ywc_kor_", "var:ywc_nqg_", "var:ywc_shu_")) and node.key.removeprefix("var:").endswith(("_pending_event", "_notice_event", "_pending")):
                exclusions.append({"queue": node.key.removeprefix("var:"), "op": node.op, "mode": "exact", "value": node.value})
            elif node.key == "has_variable" and node.value.startswith(("ywc_kor_", "ywc_nqg_", "ywc_shu_")) and node.value.endswith(("_pending_event", "_notice_event", "_pending")):
                exclusions.append({"queue": node.value, "op": node.op, "mode": "presence"})
    visit(children(limits[0]))
    return exclusions


def _lan_queue_candidates(branch_source: str) -> list[dict[str, Any]]:
    """Parse LAN's deliberately narrow positive queue predicate grammar."""
    roots = parse_block("{ " + branch_source + " }")
    if len(roots) != 1 or roots[0].key not in {"if", "else_if"}:
        raise ValueError("LAN source site must be one if/else_if branch")
    limits = direct_values(children(roots[0]), "limit")
    if len(limits) != 1:
        raise ValueError("LAN sender branch must have exactly one limit")
    found: list[dict[str, Any]] = []
    def visit(items: tuple[Node, ...], excluded: bool = False, nested_logic: bool = False) -> None:
        for node in items:
            negative = excluded or node.key == "NOT"
            if isinstance(node.value, tuple):
                if node.key not in {"AND", "NOT", "limit"}:
                    raise ValueError(f"LAN queue dispatch does not support Boolean/container {node.key}")
                if node.key == "NOT" and excluded:
                    raise ValueError("LAN queue dispatch does not support nested negative queue logic")
                visit(node.value, negative, nested_logic or node.key in {"OR", "XOR"})
                continue
            if negative:
                continue
            if node.key == "has_variable" and isinstance(node.value, str) and node.value.startswith("ywc_") and node.value.endswith(("_pending_event", "_notice_event")):
                if not re.fullmatch(r"ywc_lan_(mine|river|fund)_(pending_event|notice_event)", node.value):
                    raise ValueError(f"LAN sender contains a foreign or unsupported queue: {node.value}")
                continue
            if not node.key.startswith("var:ywc_lan_"):
                if node.key.startswith("var:ywc_") and node.key.removeprefix("var:").endswith(("_pending_event", "_notice_event")):
                    raise ValueError(f"LAN sender contains a foreign or unsupported queue: {node.key}")
                continue
            queue = node.key.removeprefix("var:")
            match = re.fullmatch(r"ywc_lan_(mine|river|fund)_(pending_event|notice_event)", queue)
            if not match:
                raise ValueError(f"LAN sender contains an unknown queue predicate: {queue}")
            if node.op != "=" or not isinstance(node.value, str) or not node.value.isdigit():
                raise ValueError(f"LAN queue predicate must be an exact integer equality: {queue}")
            value = int(node.value)
            kind = "normal" if match.group(2) == "pending_event" else "notice"
            if kind == "notice" and value not in {12, 36}:
                raise ValueError(f"LAN notice queue must equal 12 or 36: {queue}={value}")
            found.append({"queue": queue, "kind": kind, "mode": "exact", "value": value})
    visit(children(limits[0]))
    if len(found) != 1:
        raise ValueError(f"each LAN sender must bind exactly one positive exact queue candidate; got {found!r}")
    return found


def _lan_queue_exclusions(branch_source: str) -> list[dict[str, Any]]:
    """Reject unsupported negative queue predicates; current LAN has none."""
    roots = parse_block("{ " + branch_source + " }")
    if len(roots) != 1 or roots[0].key not in {"if", "else_if"}:
        raise ValueError("LAN source site must be one if/else_if branch")
    limits = direct_values(children(roots[0]), "limit")
    if len(limits) != 1:
        raise ValueError("LAN sender branch must have exactly one limit")
    negative: list[dict[str, Any]] = []
    def visit(items: tuple[Node, ...], under_not: bool = False) -> None:
        for node in items:
            neg = under_not or node.key == "NOT"
            if isinstance(node.value, tuple):
                visit(node.value, neg); continue
            is_queue = (node.key.startswith("var:ywc_") and node.key.removeprefix("var:").endswith(("_pending_event", "_notice_event"))) or (node.key == "has_variable" and isinstance(node.value, str) and node.value.startswith("ywc_") and node.value.endswith(("_pending_event", "_notice_event")))
            if neg and is_queue:
                raise ValueError("LAN source contains an unsupported negative queue predicate")
    visit(children(limits[0]))
    return negative


def _kor_source_binding(journal_id: str, pulse: str, *, candidate_parser=_kor_queue_candidates, exclusion_parser=_kor_queue_exclusions) -> dict[str, Any]:
    """Bind each native KOR sender, its chain and all earlier-branch predicates."""
    top = parse_block(pulse)
    monthly = direct_values(top, "on_monthly_pulse")
    if len(monthly) != 1:
        raise ValueError(f"{journal_id}: expected one monthly pulse")
    effects = direct_values(children(monthly[0]), "effect")
    if len(effects) != 1:
        raise ValueError(f"{journal_id}: monthly pulse must contain one effect")
    nodes = children(effects[0])
    entries: list[dict[str, Any]] = []
    chain_id = -1
    previous_branch: Node | None = None
    previous_sources: list[dict[str, Any]] = []
    event_spans: set[tuple[int, int]] = set()
    for ordinal, node in enumerate(nodes):
        branch = node.key in {"if", "else_if"}
        if node.key == "else_if" and previous_branch is None:
            raise ValueError(f"{journal_id}: orphan else_if at source ordinal {ordinal}")
        if node.key == "if":
            chain_id += 1
            previous_sources = []
        previous_branch = node if branch else None
        ids = trigger_event_ids((node,)) if branch else []
        if not ids:
            if not branch and trigger_event_ids((node,)):
                raise ValueError(f"{journal_id}: trigger_event outside a supported sender branch")
            if branch:
                limit_nodes = direct_values(children(node), "limit")
                if len(limit_nodes) == 1:
                    previous_sources.append({"ordinal": ordinal, "sha256": block_digest(node, pulse), "limit_sha256": block_digest(limit_nodes[0], pulse), "limit_source": render_node(limit_nodes[0], pulse)})
            continue
        direct_events = direct_values(children(node), "trigger_event")
        limits = direct_values(children(node), "limit")
        if len(ids) != 1 or len(direct_events) != 1 or len(limits) != 1:
            raise ValueError(f"{journal_id}: sender must have one direct trigger_event and one direct limit")
        event_spans.add((direct_events[0].start, direct_events[0].end))
        branch_source = render_node(node, pulse)
        limit_source = render_node(limits[0], pulse)
        chain_context = [{"ordinal": row["ordinal"], "sha256": row["sha256"], "limit_sha256": row["limit_sha256"], "limit_source": row["limit_source"]} for row in previous_sources]
        entry = {"branch_index": len(entries), "statement_ordinal": ordinal, "chain_index": chain_id,
                 "branch_kind": node.key, "event": ids[0], "start": node.start, "end": node.end,
                 "sha256": block_digest(node, pulse), "limit_start": limits[0].start, "limit_end": limits[0].end,
                 "limit_sha256": block_digest(limits[0], pulse), "limit_source": limit_source,
                 "chain_prior": chain_context, "chain_sha256": hashlib.sha256(repr(chain_context).encode()).hexdigest(),
                 "candidates": candidate_parser(branch_source), "queue_exclusions": exclusion_parser(branch_source)}
        entries.append(entry)
        previous_sources.append({"ordinal": ordinal, "sha256": entry["sha256"], "limit_sha256": entry["limit_sha256"], "limit_source": limit_source})
    actual: list[tuple[int, int]] = []
    for node in _walk(nodes):
        if node.key == "trigger_event":
            actual.append((node.start, node.end))
    if sorted(actual) != sorted(event_spans):
        raise ValueError(f"{journal_id}: unsupported or duplicated trigger_event source site")
    return {"journal": journal_id, "branches": entries}


def _mgl_queue_candidates(branch_source: str) -> list[dict[str, Any]]:
    """Bind one MGL sender to its exact queue predicate; queue name owns kind."""
    roots = parse_block("{ " + branch_source + " }")
    if len(roots) != 1 or roots[0].key not in {"if", "else_if"}:
        raise ValueError("MGL source site must be one if/else_if branch")
    limits = direct_values(children(roots[0]), "limit")
    if len(limits) != 1:
        raise ValueError("MGL sender must have exactly one limit")
    found: list[dict[str, Any]] = []
    def visit(items: tuple[Node, ...], negative: bool = False) -> None:
        for node in items:
            if node.key in {"OR", "XOR", "NOR"}:
                raise ValueError(f"unsupported MGL queue Boolean/container {node.key}")
            is_negative = negative or node.key == "NOT"
            if isinstance(node.value, tuple):
                visit(node.value, is_negative)
                continue
            if is_negative or not node.key.startswith("var:ywc_mgl_") or node.op != "=" or not isinstance(node.value, str) or not node.value.isdigit():
                continue
            queue = node.key.removeprefix("var:")
            if queue.endswith("_pending_event"):
                kind = "normal"
            elif queue.endswith(("_blocked_12_notice_event", "_blocked_36_notice_event")):
                kind = "notice"
            else:
                continue
            found.append({"queue": queue, "kind": kind, "mode": "exact", "value": int(node.value)})
    visit(children(limits[0]))
    if len(found) != 1:
        raise ValueError(f"MGL sender must have one positive exact source queue predicate; got {found!r}")
    return found


def _mgl_source_binding(journal_id: str, pulse: str) -> dict[str, Any]:
    """Bind MGL's flat monthly sender chain, retaining full predecessor ASTs."""
    bound = _kor_source_binding(journal_id, pulse, candidate_parser=_mgl_queue_candidates,
                                exclusion_parser=lambda _src: [])
    top = parse_block(pulse)
    monthly = direct_values(top, "on_monthly_pulse")
    effects = direct_values(children(monthly[0]), "effect") if len(monthly) == 1 else []
    if len(effects) != 1:
        raise ValueError(f"{journal_id}: expected exactly one monthly pulse effect")
    nodes = children(effects[0])
    out = []
    for source in bound["branches"]:
        node = next((item for item in nodes if item.start == source["start"] and item.end == source["end"]), None)
        if node is None:
            raise ValueError(f"{journal_id}: MGL sender source span was lost")
        source_text = render_node(node, pulse)
        out.append({**source, "statement_ordinal": nodes.index(node), "chain_index": 0,
                    "branch_kind": node.key, "candidates": _mgl_queue_candidates(source_text),
                    "queue_exclusions": []})
    return {"journal": journal_id, "branches": out}


def _nmg_queue_candidates(branch_source: str) -> list[dict[str, Any]]:
    roots = parse_block("{ " + branch_source + " }")
    if len(roots) != 1 or roots[0].key not in {"if", "else_if"}:
        raise ValueError("NMG source site must be one if/else_if branch")
    limits = direct_values(children(roots[0]), "limit")
    if len(limits) != 1:
        raise ValueError("NMG sender must have exactly one limit")
    found = []
    def visit(items, excluded=False):
        for node in items:
            negative = excluded or node.key == "NOT"
            if isinstance(node.value, tuple):
                if node.key in {"OR", "XOR", "NOR"}:
                    raise ValueError(f"unsupported NMG queue Boolean/container {node.key}")
                visit(node.value, negative)
            elif not negative and node.key.startswith("var:ywc_nmg_") and node.op == "=" and isinstance(node.value, str) and node.value.isdigit() and node.key.endswith(("_pending", "_notice_pending")):
                queue = node.key.removeprefix("var:")
                found.append({"queue": queue, "kind": "notice" if queue.endswith("_notice_pending") else "normal", "mode": "exact", "value": int(node.value)})
    visit(children(limits[0]))
    if len(found) != 1:
        raise ValueError(f"NMG sender must contain one positive exact queue predicate; got {found!r}")
    return found


def _nmg_queue_exclusions(branch_source: str) -> list[dict[str, Any]]:
    roots = parse_block("{ " + branch_source + " }")
    if len(roots) != 1 or roots[0].key not in {"if", "else_if"}:
        raise ValueError("NMG source site must be one if/else_if branch")
    limits = direct_values(children(roots[0]), "limit")
    if len(limits) != 1:
        raise ValueError("NMG sender must have exactly one limit")
    out = []
    def visit(items, negative=False):
        for node in items:
            neg = negative or node.key == "NOT"
            if isinstance(node.value, tuple):
                if node.key in {"OR", "XOR", "NOR"}:
                    raise ValueError(f"unsupported NMG Boolean queue container {node.key}")
                visit(node.value, neg)
            elif neg and node.key.startswith("var:ywc_nmg_") and node.key.endswith(("_pending", "_notice_pending")):
                out.append({"queue": node.key.removeprefix("var:"), "op": node.op, "mode": "exact", "value": node.value})
            elif neg and node.key == "has_variable" and isinstance(node.value, str) and node.value.startswith("ywc_nmg_") and node.value.endswith(("_pending", "_notice_pending")):
                out.append({"queue": node.value, "op": node.op, "mode": "presence"})
    visit(children(limits[0]))
    return out


def _nmg_source_binding(journal_id: str, pulse: str) -> dict[str, Any]:
    """Bind NMG senders from their original nested monthly AST, including ancestors."""
    top = parse_block(pulse)
    monthly = direct_values(top, "on_monthly_pulse")
    if len(monthly) != 1: raise ValueError(f"{journal_id}: expected one monthly pulse")
    effects = direct_values(children(monthly[0]), "effect")
    if len(effects) != 1: raise ValueError(f"{journal_id}: monthly pulse must have one effect")
    root_source = pulse
    rows = []; chain_counter = 0
    all_spans = []
    def siblings(nodes, ancestors=(), chain_prior=(), active_chain=None, outer_priors=()):
        nonlocal chain_counter
        prior = [] if active_chain is None else list(chain_prior)
        current_chain = active_chain
        chain_position = 0
        prev_branch = False
        for ordinal, node in enumerate(nodes):
            if node.key == "if":
                current_chain = chain_counter; chain_counter += 1; prior = list(outer_priors); chain_position = 0; prev_branch = True
            elif node.key == "else_if":
                if not prev_branch: raise ValueError(f"{journal_id}: orphan else_if")
                prev_branch = True
            elif node.key == "else":
                prev_branch = False
                siblings(children(node), ancestors + (node,), (), None,
                         [{**p, "ordinal": p["ordinal"] + 1} for p in prior])
                continue
            else:
                prev_branch = False
                if isinstance(node.value, tuple): siblings(children(node), ancestors, (), None)
                continue
            ids = trigger_event_ids((node,))
            limits = direct_values(children(node), "limit")
            if ids:
                triggers = direct_values(children(node), "trigger_event")
                if len(ids) != 1 or len(triggers) != 1 or len(limits) != 1:
                    raise ValueError(f"{journal_id}: NMG sender requires one direct trigger and one limit")
                all_spans.append((triggers[0].start, triggers[0].end))
                branch_source = render_node(node, root_source)
                limit_source = render_node(limits[0], root_source)
                priors = [{"ordinal": p["ordinal"], "sha256": p["sha256"], "limit_sha256": p["limit_sha256"], "limit_source": p["limit_source"]} for p in prior]
                row = {"branch_index": len(rows), "statement_ordinal": ordinal, "chain_index": current_chain if current_chain is not None else chain_counter,
                    "branch_kind": node.key, "event": ids[0], "start": node.start, "end": node.end,
                    "sha256": block_digest(node, root_source), "limit_start": limits[0].start, "limit_end": limits[0].end,
                    "limit_sha256": block_digest(limits[0], root_source), "limit_source": limit_source,
                    "chain_prior": priors, "candidates": _nmg_queue_candidates(branch_source), "queue_exclusions": _nmg_queue_exclusions(branch_source)}
                # The full enclosing native `else` and its outer notice chain are part
                # of a nested normal chain's source identity.
                context = [render_node(a, root_source) for a in ancestors]
                enclosing = hashlib.sha256(context[-1].encode()).hexdigest() if context else None
                row["chain_sha256"] = hashlib.sha256((repr(priors) if not enclosing else repr({"chain_prior": priors, "enclosing_else_sha256": enclosing})).encode()).hexdigest()
                rows.append(row)
                chain_position += 1
            if limits:
                prior.append({"ordinal": chain_position - 1,
                    "sha256": block_digest(node, root_source), "limit_sha256": block_digest(limits[0], root_source), "limit_source": render_node(limits[0], root_source)})
            # NMG's notice->else contains one separate normal if/else_if chain.
            for child in children(node):
                if child.key == "else": siblings(children(child), ancestors + (child,), (), None,
                    [{**p, "ordinal": p["ordinal"] + 1} for p in prior])
    siblings(children(effects[0]))
    actual = [(n.start, n.end) for n in _walk(children(effects[0])) if n.key == "trigger_event"]
    if sorted(actual) != sorted(all_spans): raise ValueError(f"{journal_id}: unsupported trigger_event outside a sender site")
    return {"journal": journal_id, "branches": rows}


def _kor_direct_adds(arc: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for event in arc["events"]:
        for option in event["options"]:
            source = option["effect"]
            nodes = [node for node in _walk(parse_block(source)) if node.key == "add_journal_entry"]
            for ordinal, node in enumerate(nodes):
                if not isinstance(node.value, tuple):
                    raise ValueError(f"{event['id']}/{option['key']}: add_journal_entry must be a block")
                values = direct_values(children(node), "type")
                if len(children(node)) != 1 or len(values) != 1 or values[0].op != "=" or not isinstance(values[0].value, str):
                    raise ValueError(f"{event['id']}/{option['key']}: add_journal_entry needs one literal type")
                records.append({"event": event["id"], "option": option["key"], "journal": values[0].value,
                                "site_ordinal": ordinal, "effect_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
                                "site_sha256": block_digest(node, source)})
    return records


_SHU_SOURCE_HASHES = {
    "ywc_je_v03_shu_register_pilot": "2e684bfe730ad4750dca58cdc0c2c7a9d09e5cd08352a6eb654adbeefcba4eb1",
    "ywc_je_v03_shu_fiscal_settlement": "c6366c199ed2e11fabaa894bcd20141ab28d43fa8c4e973d42038dcddf581b45",
    "ywc_je_v03_shu_service_contract": "b5b8acdee5f291e52e7ad35a94611fcab5104263c56f85ff4f5835c223fd174f",
    "ywc_je_v03_shu_service_appointments": "bd5a2562cdf059f0267f81c2766ba9eac7e1e119d72876d5f644571242779b16",
    "ywc_je_v03_shu_service_successor": "8063472bcaecbc2db0b782e270dcb8e2a1c6b89671e6e0204725d7791cce4b4d",
    "ywc_je_v03_shu_port_customs": "8a69d7f45b08fce68c41036ace18ba713e2c2171cb261928ed682f04ccb585e9",
}

_SHU_IMMEDIATE_HASHES = {
    "ywc_shu.1000": "e0fe55071f787ac81ebe848acb5799cbde2b40c2be3aef64a22074374798fb14",
    "ywc_shu.1001": "1e868c016421ee22b58d67947b9cd9499fa7b3cdd5b9f307eb00c113db633529",
    "ywc_shu.1002": "a82033c3f8603462ea76ae9ee123b027738ef378d8f6072116bc468f8dbd2459",
    "ywc_shu.1003": "b697228bbdefa90c3a2e00e297bc8d05d68bea49865019c987dcfe035e777b7e",
    "ywc_shu.1004": "0f3c810fd76b339f86482babe6d0e42fba425c77c3114f7bf8e2b91c7e7845be",
    "ywc_shu.1005": "28d2f390baf16a3ce63cbad14f87a9373d5689be8de17e6c7076f07d255a0fec",
    "ywc_shu.1006": "8f3877cef81389e2efab8e1df0c87dd7822a2e8bb1a205c3c4078314b6d63a92",
    "ywc_shu.1007": "f95e71eb78aa30f39d573b02e59a45fa5e73f11f1f48d0fd17a7d818e48b018e",
    "ywc_shu.1008": "666459042417076f308b92d9c4e9518a4679813cbd2a39e3be0b4daf562bb751",
    "ywc_shu.1009": "dc2ff92f7860562000c5c75d566dc88b6eef1ce876b3e0bc17cad5403112dc03",
    "ywc_shu.1010": "0ea9a790b85c09cf3b52dc071717ba4f2ca4c36834b30174c82ff7fa76352182",
    "ywc_shu.1011": "aeb853e8c7e6ef7390fce8e25c41f69537342916bae063d332c1ba1d40ba092d",
    "ywc_shu.1012": "65bc3271ababc6004de7c04c3b844c25ce342a173774065bf6c07dd1279b01e1",
    "ywc_shu.1013": "c202584dbc887930514e2c90ab1c21be470671796a5b8f40fced00d96643bfb7",
    "ywc_shu.1014": "2e0173d4ff4c437ceed89607a847baa0fdeab4c9c02b840997548442b1da74a8",
    "ywc_shu.1015": "eb1fa9b661263ff4ba26c00b4c25fc4dc1a20bb1ac0a0d4cb50c3296188e3d83",
    "ywc_shu.1016": "9bceac36b907d9751e68448427b1a50bc187618a8eba029fcc50163ea41ecee1",
    "ywc_shu.1017": "caff16ec7fc375553a49fe71f02d81f79bf5488558885667d3a95591f7550817",
    "ywc_shu.1018": "9362934ea8a50f8e448126c372b49e101747ceccb0b6bd769be194f328c30069",
    "ywc_shu.1019": "63e4c6f8d4bd0675276fa6146c9aaad7f5af16cbba8d545040f40c89f1b0dc39",
    "ywc_shu.1020": "92ba2da3bc3c60570dccfbebb4e4b140a3f454a69b68af322437e647da48a53d",
    "ywc_shu.1021": "ec3ca968f8bb30d848e77b2084ad347ea5375df8187bcfdf05cfd0bab2901adf",
    "ywc_shu.1022": "ef10aea6dd7349bdd27cadc07aa6fa8832fc5c96be1d567bbc36b27bf127c52e",
    "ywc_shu.1023": "5378b52b333f4cc761568e59847471e22e250de43fc9b11b1456f8c5140e3ce5",
    "ywc_shu.1024": "f3d887ca608207751d2500c6baac87b97542fe90edde92fd2fe4d82d9901cccd",
    "ywc_shu.1025": "b97c714952972e970403690a2ff0939945f6ec4c9b32eb13af976eb2ddd06902",
}

_SHU_DIRECT_ADD_BASELINE = [
    {"event": "ywc_shu.1015", "option": "accept_appointments", "journal": "ywc_je_v03_shu_service_successor", "site_ordinal": 0,
     "effect_sha256": "5b0b1e26a30b02f1c6a262da25a41bc0098a62ed591bac14c59f85bfe7af1ae0",
     "site_sha256": "354248736cc530bba146536e6626c3e92e0a7dc1f20fc82816e6b41631746203"},
]


_SHU_FOUNDATION_SLUGS = (
    "v03_shu_fiscal_register", "v03_shu_service_compact", "v03_shu_port_treasury",
)
_SHU_MIDDLE_SLUG = "v03_shu_provincial_contract"
# Filled only from reviewed authored sources, never from mutable metadata.
_SHU_MIDDLE_SOURCE_HASHES: dict[str, str] = {
    "ywc_je_v03_shu_provincial_charter": "31ada106f54d24b24fbf0f569759cfb7aa00ee1b7fc70bdb9e2ef0d74b6cc057",
    "ywc_je_v03_shu_provincial_ledger": "7dea3b477395ef96ca9d92ad86034d83458e94412549799c1970850b31e33c98"
}
_SHU_MIDDLE_IMMEDIATE_HASHES: dict[str, str] = {
    "ywc_shu.1100": "1cef687fb42c4721b4a9506efd093fb3f5244c72f74ea8a126a942c61499fc71",
    "ywc_shu.1101": "8dc728707e3396903142eeed216c7f5fd172c654145cac4fcfaed2ab982edcca",
    "ywc_shu.1102": "0c4e678451c6ffa8eeece72672a451ce26a919d6ceac3459e0c8e44aa86809e9",
    "ywc_shu.1103": "b6f826da6d2cf44275b61061ce8f3d6224c1ac5522233978c2bea0007921e1bb",
    "ywc_shu.1104": "5f11f290b4577a6f46c26606df326921ca10618047120e5e49cd528f447f2d72",
    "ywc_shu.1105": "a219eca989b6143382b125ab4677bd8cf65e76b21aacc2128dc059df48dec030",
    "ywc_shu.1106": "3b66aeb131b771f516ff8867b812bcdf2f194047575c493530a7bbf6eb30587d",
    "ywc_shu.1107": "534845181a7d98079ed085c99210e5b139aaacd80f99b44d175afc06987a057d"
}


def _shu_active_arcs(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    foundation = [arc for arc in catalog["arcs"]
                  if isinstance(arc, dict) and arc.get("era") == "foundation"]
    if len(foundation) != 3 or {arc.get("slug") for arc in foundation} != set(_SHU_FOUNDATION_SLUGS):
        raise ValueError("SHU inline adapter requires exactly its three foundation arcs")
    extra = [arc for arc in catalog["arcs"] if arc not in foundation]
    for arc in extra:
        if not isinstance(arc, dict) or arc.get("slug") != _SHU_MIDDLE_SLUG or arc.get("era") != "middle":
            slug = arc.get("slug") if isinstance(arc, dict) else None
            raise ValueError(f"unregistered SHU inline arc: {slug}")
    if len(extra) > 1:
        raise ValueError("SHU inline adapter permits one registered provincial-contract arc")
    # Append middle sites after the original 31, regardless of catalog order.
    return [next(arc for arc in foundation if arc["slug"] == slug)
            for slug in _SHU_FOUNDATION_SLUGS] + extra


def _shu_expected_receipt(event_id: str) -> tuple[str, int]:
    match = re.fullmatch(r"ywc_shu\.(10(?:0[0-9]|1[0-9]|2[0-5])|110[0-7])", event_id)
    if not match:
        raise ValueError(f"unsupported SHU native event receipt owner: {event_id}")
    number = int(match.group(1))
    if number <= 1009:
        return "ywc_v03_shu_v03_shu_fiscal_register_last_event", number - 999
    return "ywc_v03_shu_event_dispatch", number


def _shu_queue_candidates(branch_source: str) -> list[dict[str, Any]]:
    """Return the native SHU queued-event and shared notice queue predicates."""
    nodes = parse_block("{ " + branch_source + " }")
    if len(nodes) != 1 or nodes[0].key not in {"if", "else_if"}:
        raise ValueError("SHU source site must be one if/else_if branch")
    limits = direct_values(children(nodes[0]), "limit")
    if len(limits) != 1:
        raise ValueError("SHU sender branch must have exactly one limit")
    found: dict[tuple[str, str, int | None], dict[str, Any]] = {}

    def visit(items: tuple[Node, ...], negative: bool = False) -> None:
        for node in items:
            blocked = negative or node.key == "NOT"
            if isinstance(node.value, tuple):
                visit(node.value, blocked)
                continue
            if blocked or not isinstance(node.value, str):
                continue
            variable = None
            mode = None
            value = None
            if node.key == "has_variable" and node.op == "=" and node.value.startswith("ywc_shu_") and node.value.endswith("_pending_event"):
                variable, mode = node.value, "presence"
            elif node.key.startswith("var:ywc_shu_") and node.op == "=" and node.value.isdigit() and node.key.endswith("_pending_event"):
                variable, mode, value = node.key.removeprefix("var:"), "exact", int(node.value)
            if variable is None:
                continue
            kind = "notice" if variable.endswith("_notice_pending_event") else "normal"
            candidate = {"queue": variable, "kind": kind, "mode": mode}
            if mode == "exact":
                candidate["value"] = value
            found[(variable, mode, value)] = candidate
    visit(children(limits[0]))
    # A queue may be both present and exact-value tested. Its exact test is
    # the dispatch identity; do not create a second presence candidate.
    selected: dict[str, dict[str, Any]] = {}
    for row in found.values():
        previous = selected.get(row["queue"])
        if previous is None or row["mode"] == "exact":
            selected[row["queue"]] = row
    return sorted(selected.values(), key=lambda row: (row["kind"], row["queue"], row.get("value", -1)))


def _validate_shu_inline_catalog(catalog: dict[str, Any]) -> None:
    """Validate SHU's exact native source sites, exclusions and immediate receipts."""
    if catalog.get("key") != "country_shu" or not isinstance(catalog.get("arcs"), list):
        raise ValueError("SHU inline adapter requires the SHU catalog")
    active = _shu_active_arcs(catalog)
    has_middle = len(active) == 4
    source_hashes = {**_SHU_SOURCE_HASHES, **(_SHU_MIDDLE_SOURCE_HASHES if has_middle else {})}
    immediate_hashes = {**_SHU_IMMEDIATE_HASHES, **(_SHU_MIDDLE_IMMEDIATE_HASHES if has_middle else {})}
    witnesses: set[str] = set()
    queues_by_arc: dict[str, set[str]] = {}
    queue_owners: dict[str, str] = {}
    total_sites = 0
    expected_event_ids: set[str] = set()
    observed_direct_adds: list[dict[str, Any]] = []
    for arc in active:
        adapter = arc.get("inline_delivery_adapter")
        if not isinstance(adapter, dict) or set(adapter) != {"schema", "live_phases", "branches", "direct_adds"} or adapter.get("schema") != "v03.foundation_inline_adapter.v3":
            raise ValueError(f"{arc['slug']}: SHU requires strict v3 inline metadata")
        journals = arc.get("journals")
        if not isinstance(journals, list) or not journals:
            raise ValueError(f"{arc['slug']}: source journals are required")
        phases = adapter["live_phases"]
        if not isinstance(phases, list) or len(phases) != len(journals):
            raise ValueError(f"{arc['slug']}: every native JE needs a phase witness")
        for phase, journal in zip(phases, journals):
            if not isinstance(phase, dict) or set(phase) != {"journal", "live_witness", "source_script_sha256", "goal_sha256", "exit_sha256"} or phase.get("journal") != journal.get("id"):
                raise ValueError(f"{arc['slug']}: malformed live phase binding")
            jid = journal["id"]
            if jid not in source_hashes or hashlib.sha256(journal["script"].encode("utf-8")).hexdigest() != source_hashes[jid]:
                raise ValueError(f"{arc['slug']}/{jid}: frozen native source script changed")
            for field, source_key in (("source_script_sha256", "script"), ("goal_sha256", "goal"), ("exit_sha256", "exit_conditions")):
                if type(phase.get(field)) is not str or phase[field] != hashlib.sha256(journal[source_key].encode("utf-8")).hexdigest():
                    raise ValueError(f"{arc['slug']}/{jid}: source {source_key} drift")
            witness = phase.get("live_witness")
            if type(witness) is not str or not re.fullmatch(r"ywc_v03_shu_inline_live_[a-z0-9_]+", witness) or witness in witnesses:
                raise ValueError(f"{arc['slug']}/{jid}: invalid or duplicate live witness")
            witnesses.add(witness)
        for event in arc.get("events", []):
            event_id = event.get("id") if isinstance(event, dict) else None
            expected_event_ids.add(event_id)
            receipt_name, receipt_value = _shu_expected_receipt(event_id)
            immediate = event.get("immediate")
            if type(immediate) is not str:
                raise ValueError(f"{arc['slug']}/{event_id}: native immediate must remain source-owned text")
            if event_id not in immediate_hashes or hashlib.sha256(immediate.encode("utf-8")).hexdigest() != immediate_hashes[event_id]:
                raise ValueError(f"{arc['slug']}/{event_id}: frozen native immediate source changed")
            immediate_nodes = parse_block(immediate)
            major_calls = [i for i, node in enumerate(immediate_nodes) if node.key == "ywc_v03_mark_major_delivered" and node.op == "=" and node.value == "yes"]
            receipts = [(i, node) for i, node in enumerate(immediate_nodes) if node.key == "set_variable" and isinstance(node.value, tuple) and len(direct_values(children(node), "name")) == 1 and direct_values(children(node), "name")[0].value == receipt_name]
            if len(major_calls) != 1 or len(receipts) != 1:
                raise ValueError(f"{arc['slug']}/{event_id}: required native receipt operations are missing or duplicated")
            values = direct_values(children(receipts[0][1]), "value")
            if receipts[0][1].op != "=" or len(values) != 1 or values[0].op != "=" or values[0].value != str(receipt_value) or major_calls[0] >= receipts[0][0]:
                raise ValueError(f"{arc['slug']}/{event_id}: actual source receipt/order drift")
        actual: list[tuple[str, dict[str, Any]]] = []
        for journal in journals:
            actual.extend((journal["id"], row) for row in _kor_source_binding(journal["id"], journal["script"], candidate_parser=_shu_queue_candidates)["branches"])
        records = adapter["branches"]
        if not isinstance(records, list) or len(records) != len(actual):
            raise ValueError(f"{arc['slug']}: every native sender site must be recorded")
        event_ids = {event["id"] for event in arc["events"]}
        for proof, (jid, source) in zip(records, actual):
            total_sites += 1
            required = {"journal", "branch_index", "statement_ordinal", "chain_index", "branch_kind", "event", "branch_sha256", "limit_sha256", "chain_prior", "chain_sha256", "candidates", "queue_exclusions", "source_ops"}
            if not isinstance(proof, dict) or set(proof) != required:
                raise ValueError(f"{arc['slug']}/{jid}: malformed sender site record")
            for field in ("branch_index", "statement_ordinal", "chain_index"):
                if type(proof.get(field)) is not int:
                    raise ValueError(f"{arc['slug']}/{jid}: {field} must be an integer")
            checks = {"journal": jid, "branch_index": source["branch_index"], "statement_ordinal": source["statement_ordinal"], "chain_index": source["chain_index"], "branch_kind": source["branch_kind"], "event": source["event"], "branch_sha256": source["sha256"], "limit_sha256": source["limit_sha256"], "chain_prior": source["chain_prior"], "chain_sha256": source["chain_sha256"], "queue_exclusions": source["queue_exclusions"]}
            if any(proof.get(field) != expected for field, expected in checks.items()):
                raise ValueError(f"{arc['slug']}/{jid}: exact source chain/site drift")
            if type(proof.get("chain_sha256")) is not str or re.fullmatch(r"[0-9a-f]{64}", proof["chain_sha256"]) is None or not isinstance(proof.get("chain_prior"), list):
                raise ValueError(f"{arc['slug']}/{jid}: malformed source-chain proof")
            for prior in proof["chain_prior"]:
                if not isinstance(prior, dict) or set(prior) != {"ordinal", "sha256", "limit_sha256", "limit_source"} or type(prior.get("ordinal")) is not int or type(prior.get("limit_source")) is not str:
                    raise ValueError(f"{arc['slug']}/{jid}: malformed source-chain prior site")
                if any(type(prior.get(field)) is not str or re.fullmatch(r"[0-9a-f]{64}", prior[field]) is None for field in ("sha256", "limit_sha256")):
                    raise ValueError(f"{arc['slug']}/{jid}: malformed source-chain prior hash")
            if not isinstance(proof.get("queue_exclusions"), list) or any(not isinstance(row, dict) or set(row) != {"queue", "op", "mode", *({"value"} if row.get("mode") == "exact" else set())} or type(row.get("queue")) is not str or type(row.get("op")) is not str or type(row.get("mode")) is not str or ("value" in row and type(row["value"]) is not str) for row in proof["queue_exclusions"]):
                raise ValueError(f"{arc['slug']}/{jid}: malformed negative queue semantics")
            if proof["event"] not in event_ids:
                raise ValueError(f"{arc['slug']}/{jid}: sender event is not arc-owned")
            expected_candidates = source["candidates"]
            if proof["candidates"] != expected_candidates:
                raise ValueError(f"{arc['slug']}/{jid}: queue semantics differ from positive native predicates")
            for candidate in proof["candidates"]:
                if not isinstance(candidate, dict) or set(candidate) != ({"queue", "kind", "mode", "value"} if candidate.get("mode") == "exact" else {"queue", "kind", "mode"}):
                    raise ValueError(f"{arc['slug']}/{jid}: malformed native queue candidate")
                if candidate["kind"] == "notice" and candidate["mode"] != "presence":
                    raise ValueError(f"{arc['slug']}/{jid}: shared notice queue must use presence semantics")
                if "value" in candidate and type(candidate["value"]) is not int:
                    raise ValueError(f"{arc['slug']}/{jid}: queue exact value must be an integer")
                owner = arc["slug"]
                queues_by_arc.setdefault(owner, set()).add(candidate["queue"])
                prior_owner = queue_owners.setdefault(candidate["queue"], owner)
                if prior_owner != owner:
                    raise ValueError(f"SHU queue ownership crosses arcs: {candidate['queue']}")
            # Bind every pre-trigger transaction operation (queue removal, auxiliary cleanup and claim).
            script = next(j["script"] for j in journals if j["id"] == jid)
            native = _branch_node(script, source)[0]
            ops = [{"key": node.key, "op": node.op, "value": node.value if isinstance(node.value, str) else render_node(node, script)} for node in children(native) if node.key not in {"limit", "trigger_event"}]
            if proof["source_ops"] != ops:
                raise ValueError(f"{arc['slug']}/{jid}: source auxiliary/queue operations drift")
        direct_adds = adapter["direct_adds"]
        if not isinstance(direct_adds, list):
            raise ValueError(f"{arc['slug']}: direct-add source inventory must be a list")
        for record in direct_adds:
            if not isinstance(record, dict) or set(record) != {"event", "option", "journal", "site_ordinal", "effect_sha256", "site_sha256"}:
                raise ValueError(f"{arc['slug']}: malformed direct-add source record")
            if type(record.get("site_ordinal")) is not int or any(type(record.get(field)) is not str for field in ("event", "option", "journal", "effect_sha256", "site_sha256")):
                raise ValueError(f"{arc['slug']}: invalid direct-add source record types")
            if any(re.fullmatch(r"[0-9a-f]{64}", record[field]) is None for field in ("effect_sha256", "site_sha256")):
                raise ValueError(f"{arc['slug']}: malformed direct-add source hashes")
        if direct_adds != _kor_direct_adds(arc):
            raise ValueError(f"{arc['slug']}: direct-add source inventory drift")
        observed_direct_adds.extend(direct_adds)
    expected_sites = 39 if has_middle else 31
    if total_sites != expected_sites:
        raise ValueError(f"SHU adapter requires exactly {expected_sites} native sender sites")
    required_ids = {f"ywc_shu.{n}" for n in range(1000, 1026)}
    if has_middle:
        required_ids |= {f"ywc_shu.{n}" for n in range(1100, 1108)}
    if expected_event_ids != required_ids:
        raise ValueError(f"SHU adapter requires exactly its {len(required_ids)} native events")
    if set(immediate_hashes) != expected_event_ids:
        raise ValueError("SHU immediate baseline pin coverage differs from native event coverage")
    if set(source_hashes) != {journal["id"] for arc in active for journal in arc["journals"]}:
        raise ValueError("SHU journal baseline pin coverage differs from native source coverage")
    if observed_direct_adds != _SHU_DIRECT_ADD_BASELINE:
        raise ValueError("SHU native direct-add caller/target baseline drift")

def _lan_source_binding(journal_id: str, pulse: str) -> dict[str, Any]:
    binding = _kor_source_binding(journal_id, pulse, candidate_parser=_lan_queue_candidates,
                                  exclusion_parser=_lan_queue_exclusions)
    for branch in binding["branches"]:
        if len(branch["candidates"]) != 1:
            raise ValueError(f"{journal_id}: LAN sender lacks one exact queue candidate")
        candidate = branch["candidates"][0]
        if candidate["kind"] == "normal" and candidate["value"] != int(branch["event"].rsplit(".", 1)[-1]):
            raise ValueError(f"{journal_id}: pending queue value must match its native event ID")
    return binding


def _validate_lan_inline_catalog(catalog: dict[str, Any]) -> None:
    """Bound LAN's exact six-JE source and native immediate contract."""
    expected_slugs = {"v03_lan_mine_accounts", "v03_lan_river_compacts", "v03_lan_work_accident_fund"}
    if catalog.get("key") != "country_lan" or not isinstance(catalog.get("arcs"), list):
        raise ValueError("LAN inline adapter requires the LAN catalog")
    active = [a for a in catalog["arcs"] if isinstance(a, dict) and a.get("era") == "foundation"]
    if len(active) != 3 or {a.get("slug") for a in active} != expected_slugs:
        raise ValueError("LAN inline adapter requires exactly its three foundation arcs")
    counts = {"ywc_je_v03_lan_mine_ledger": 7, "ywc_je_v03_lan_mine_settlement": 5,
              "ywc_je_v03_lan_river_compacts": 8, "ywc_je_v03_lan_river_settlement": 4,
              "ywc_je_v03_lan_accident_fund": 7, "ywc_je_v03_lan_fund_settlement": 5}
    all_events: set[str] = set()
    witnesses: set[str] = set()
    modes = {"normal": 0, "notice12": 0, "notice36": 0}
    for arc in active:
        adapter = arc.get("inline_delivery_adapter")
        if not isinstance(adapter, dict) or set(adapter) != {"schema", "live_phases", "branches", "direct_adds"} or adapter.get("schema") != "v03.foundation_inline_adapter.v2":
            raise ValueError(f"{arc['slug']}: LAN requires strict v2 inline metadata")
        journals = arc.get("journals")
        if not isinstance(journals, list) or not journals:
            raise ValueError(f"{arc['slug']}: source journals are required")
        phases = adapter["live_phases"]
        if not isinstance(phases, list) or len(phases) != len(journals):
            raise ValueError(f"{arc['slug']}: every source JE needs one live phase")
        for phase, journal in zip(phases, journals):
            if not isinstance(phase, dict) or set(phase) != {"journal", "live_witness", "source_script_sha256", "goal_sha256", "exit_sha256"} or phase.get("journal") != journal.get("id"):
                raise ValueError(f"{arc['slug']}: malformed LAN live phase binding")
            for field, source_key in (("source_script_sha256", "script"), ("goal_sha256", "goal"), ("exit_sha256", "exit_conditions")):
                if type(phase.get(field)) is not str or phase[field] != hashlib.sha256(journal[source_key].encode()).hexdigest():
                    raise ValueError(f"{arc['slug']}/{journal['id']}: LAN source {source_key} drift")
            witness = phase["live_witness"]
            if type(witness) is not str or not re.fullmatch(r"ywc_v03_lan_inline_live_[a-z0-9_]+", witness) or witness in witnesses:
                raise ValueError(f"{arc['slug']}/{journal['id']}: invalid LAN live witness")
            witnesses.add(witness)
        expected: list[tuple[str, dict[str, Any]]] = []
        for journal in journals:
            expected.extend((journal["id"], row) for row in _lan_source_binding(journal["id"], journal["script"])["branches"])
        records = adapter["branches"]
        if not isinstance(records, list) or len(records) != len(expected):
            raise ValueError(f"{arc['slug']}: all LAN sender sites must be bound")
        event_ids = {e.get("id") for e in arc.get("events", []) if isinstance(e, dict)}
        expected_base={"v03_lan_mine_accounts":1000,"v03_lan_river_compacts":1010,"v03_lan_work_accident_fund":1020}[arc["slug"]]
        if event_ids != {f"ywc_lan.{n}" for n in range(expected_base,expected_base+8)}:
            raise ValueError(f"{arc['slug']}: LAN native event inventory drift")
        all_events |= event_ids
        for proof, (jid, source) in zip(records, expected):
            required = {"journal", "branch_index", "statement_ordinal", "chain_index", "branch_kind", "event", "branch_sha256", "limit_sha256", "chain_prior", "chain_sha256", "candidates", "queue_exclusions"}
            if not isinstance(proof, dict) or set(proof) != required:
                raise ValueError(f"{arc['slug']}/{jid}: malformed LAN sender record")
            checks = {"journal": jid, "branch_index": source["branch_index"], "statement_ordinal": source["statement_ordinal"], "chain_index": source["chain_index"], "branch_kind": source["branch_kind"], "event": source["event"], "branch_sha256": source["sha256"], "limit_sha256": source["limit_sha256"], "chain_prior": source["chain_prior"], "chain_sha256": source["chain_sha256"], "candidates": source["candidates"], "queue_exclusions": source["queue_exclusions"]}
            if any(proof.get(k) != v for k, v in checks.items()) or any(type(proof.get(k)) is not int for k in ("branch_index", "statement_ordinal", "chain_index")):
                raise ValueError(f"{arc['slug']}/{jid}: LAN source branch/chain binding drift")
            if proof["event"] not in event_ids:
                raise ValueError(f"{arc['slug']}/{jid}: LAN sender event is not owned by its arc")
            cand = proof["candidates"][0]
            stem = re.match(r"ywc_lan_(mine|river|fund)_", cand["queue"])
            expected_stem = {"v03_lan_mine_accounts": "mine", "v03_lan_river_compacts": "river", "v03_lan_work_accident_fund": "fund"}[arc["slug"]]
            if not stem or stem.group(1) != expected_stem or cand["mode"] != "exact":
                raise ValueError(f"{arc['slug']}/{jid}: LAN queue is not exact and arc-owned")
            if cand["kind"] == "notice":
                if cand["queue"] != f"ywc_lan_{expected_stem}_notice_event" or cand["value"] not in {12, 36}:
                    raise ValueError(f"{arc['slug']}/{jid}: malformed LAN notice queue")
                modes[f"notice{cand['value']}"] += 1
            elif cand["kind"] == "normal" and cand["queue"] == f"ywc_lan_{expected_stem}_pending_event":
                modes["normal"] += 1
            else:
                raise ValueError(f"{arc['slug']}/{jid}: unsupported LAN queue kind")
            script = next(j["script"] for j in journals if j["id"] == jid)
            node = _branch_node(script, source)[0]
            ops = [n for n in children(node) if n.key not in {"limit", "trigger_event"}]
            expected_ops = (["remove_variable"] if cand["kind"] == "normal" else ["remove_variable", "set_variable", "set_variable"])
            if [n.key for n in ops] != expected_ops:
                raise ValueError(f"{arc['slug']}/{jid}: unsupported LAN native pre-trigger operations")
            first_fields = children(ops[0]) if isinstance(ops[0].value, tuple) else ()
            if ops[0].op != "=" or len(first_fields) != 0 or ops[0].value != cand["queue"]:
                raise ValueError(f"{arc['slug']}/{jid}: LAN sender must remove only its selected queue")
            if cand["kind"] == "notice":
                values = []
                for n in ops[1:]:
                    fields = children(n)
                    names, vals = direct_values(fields, "name"), direct_values(fields, "value")
                    if (n.op != "=" or len(fields) != 2 or any(field.key not in {"name", "value"} or field.op != "=" for field in fields)
                            or len(names) != 1 or names[0].op != "=" or len(vals) != 1 or vals[0].op != "=" or not isinstance(vals[0].value, str)):
                        raise ValueError(f"{arc['slug']}/{jid}: malformed LAN notice write")
                    values.append((names[0].value, vals[0].value))
                suffix = "12" if cand["value"] == 12 else "36"
                if values != [(f"ywc_lan_{expected_stem}_notice_current", str(cand["value"])), (f"ywc_lan_{expected_stem}_notice{suffix}_sent", "1")]:
                    raise ValueError(f"{arc['slug']}/{jid}: LAN notice writes/order drift")
        direct_adds = adapter["direct_adds"]
        if not isinstance(direct_adds, list) or direct_adds != _kor_direct_adds(arc):
            raise ValueError(f"{arc['slug']}: LAN direct-add inventory drift")
        if len(expected) != counts.get(journals[0]["id"], -1) + (counts.get(journals[1]["id"], -1) if len(journals) > 1 else 0):
            raise ValueError(f"{arc['slug']}: LAN source sender count drift")
        for event in arc.get("events", []):
            if not isinstance(event, dict) or not re.fullmatch(r"ywc_lan\.(100[0-7]|101[0-7]|102[0-7])", event.get("id", "")):
                continue
            trigger = parse_block(event.get("trigger", ""))
            if len(trigger) != 2 or [(n.key,n.op,n.value) for n in trigger] != [("c:LAN","?=","this"),("ywc_v03_can_deliver_major","=","yes")]:
                raise ValueError(f"{arc['slug']}/{event['id']}: LAN native trigger drift")
            if event.get("immediate") != "{ ywc_v03_mark_major_delivered = yes }":
                raise ValueError(f"{arc['slug']}/{event['id']}: LAN native immediate must remain the pinned complete body")
    if modes != {"normal": 24, "notice12": 6, "notice36": 6}:
        raise ValueError(f"LAN sender class inventory drift: {modes}")


def validate_lan_native_helper_source(source: str) -> None:
    """Require LAN's unchanged, full 90-day native cooldown helper AST."""
    if not isinstance(source, str):
        raise ValueError("LAN native helper source must be text")
    source = source.removeprefix("\ufeff")
    try:
        definitions = parse_block("{\n" + source + "\n}")
    except (TypeError, ValueError) as exc:
        raise ValueError(f"LAN native helper source is not a complete script: {exc}") from exc
    helpers = [node for node in definitions if node.key == "ywc_v03_mark_major_delivered"]
    if len(helpers) != 1:
        raise ValueError(f"LAN native cooldown helper must have exactly one top-level definition; got {len(helpers)}")
    helper = helpers[0]
    if helper.op != "=" or not isinstance(helper.value, tuple):
        raise ValueError("LAN native cooldown helper definition must use an equals block")
    if len(helper.value) != 1 or helper.value[0].key != "if" or helper.value[0].op != "=":
        raise ValueError("LAN native cooldown helper AST changed")
    inner = children(helper.value[0])
    limits = direct_values(inner, "limit")
    sets = direct_values(inner, "set_variable")
    if len(limits) != 1 or len(sets) != 1 or len(inner) != 2 or any(n.key not in {"limit", "set_variable"} or n.op != "=" for n in inner):
        raise ValueError("LAN native cooldown helper operation inventory changed")
    lim = children(limits[0]); neg = direct_values(lim, "NOT")
    if limits[0].op != "=" or len(lim) != 1 or len(neg) != 1 or neg[0].op != "=" or len(children(neg[0])) != 1:
        raise ValueError("LAN native cooldown helper guard changed")
    guarded = children(neg[0])[0]
    if guarded.key != "has_variable" or guarded.op != "=" or guarded.value != "ywc_v03_major_event_cooldown":
        raise ValueError("LAN native cooldown helper guard changed")
    set_fields = children(sets[0]); names = direct_values(set_fields, "name"); values = direct_values(set_fields, "value"); days = direct_values(set_fields, "days")
    if (sets[0].op != "=" or len(set_fields) != 3 or any(n.key not in {"name", "value", "days"} or n.op != "=" for n in set_fields)
            or len(names) != 1 or names[0].value != "ywc_v03_major_event_cooldown"
            or len(values) != 1 or values[0].value != "1" or len(days) != 1 or days[0].value != "90"):
        raise ValueError("LAN native cooldown helper effect changed")


_MGL_JOURNAL_SHA256 = {
    "ywc_je_v03_mgl_roads_register": ("c7edcbf5a0e1702e0d025fb234bdea8ece643a2dedccada3afc3e6acad42cab8", "2a5605fa9efca852e3f45d8f93b548fb10e3645631f8974d0c66dc1339b3a4cd", "f9d6a68d2deb4dd0cc0e3f659f318f9546624fca3c8490fc244986391e53e5e5"),
    "ywc_je_v03_mgl_roads_review": ("c7e26ac7e2d54375cc725780fdfe8b3f6950f3690601dab4120d2576c6404671", "10c3d1c1cc02dca15fd09a2272133a39ad1121ed240a7f4efc8651a50ef285dd", "f9d6a68d2deb4dd0cc0e3f659f318f9546624fca3c8490fc244986391e53e5e5"),
    "ywc_je_v03_mgl_debt_register": ("5904164e5d12901d6f2acaa83bbd58d616ab8f56aec06f372f1253f9feb8242b", "bc766f8736bfdb726eabbea42efad339da61180b87ce86023f79509f7e202985", "9fd4f6eb93eb0141c3d5c4a2b4491a7ed1b99560e84ec1bbfe7ff63f712740ad"),
    "ywc_je_v03_mgl_debt_review": ("bed570184eb79a8d7211eeb6cb943ec29866fd93ab4885252fcc36d961325f7f", "81485e63f5eaff9048a83ce517d8e23b7b2c655f9a1419a2692219c4965fd1e3", "9fd4f6eb93eb0141c3d5c4a2b4491a7ed1b99560e84ec1bbfe7ff63f712740ad"),
    "ywc_je_v03_mgl_grain_register": ("18db800cebefb5a42bdb3b1b927e29f400d90c1bb2d003aa5696c8ec6778d20d", "d93925d377f35c15bf774d37d7c2ac61a576c81f833e4a36cd26547d4ce0d51f", "03edf9b9633f151b999ed97f2f05eac13e9b96b28ae8fce68e93f5905c53efd8"),
    "ywc_je_v03_mgl_grain_review": ("3d0fd162a58964cf58ab385d7a10634249d123525fb64ec7022d28c863ae1f10", "32aa32a3bff0d953201d7c81ece335a4934e674975b32dfcfd1830ca15075a3a", "03edf9b9633f151b999ed97f2f05eac13e9b96b28ae8fce68e93f5905c53efd8"),
}
_MGL_EVENT_AST_SHA256 = {
    "ywc_mng.1005": "03139b5b6e4c470075e4f410f00c44f0ffa8d27ffdbde594d36afb20d4ab3490",
    "ywc_mng.1015": "08719bb26d3732e53c1e53a27580d4942ef7e66959e8dfc9e256d6bfd8f8c818",
    "ywc_mng.1025": "38afd922adcdb693fed06e87603ecceb333c8a56135ed97180b94a65b2569420",
    **{f"ywc_mng.{n}": "4c2d62dd649e12e6b2ee771fcaee2d62b8063c145521792c52cb4e47c8fb3440"
       for n in (*range(1000, 1005), 1006, 1007, *range(1010, 1015), 1016, 1017,
                 *range(1020, 1025), 1026, 1027)},
}
_MGL_HELPER_AST_SHA256 = {
    "ywc_mgl_roads_any_affordable_entry_offer": "9ece4fdcd6f5312a9c89b66ed20678ff97e902bddf846afe4ff5415f5925ffb9",
    "ywc_mgl_roads_selected_current_obligation": "e8908d6adfdbdfa24d3766fb600b2e7e592838b61626e398980e35f42d1df882",
    "ywc_mgl_roads_current_obligation_ready": "1519fdf9f228bf4fd68d97fcb46d1c6e2015dec76893305e8cb1ac99c4c7f849",
    "ywc_mgl_debt_any_affordable_entry_offer": "89cebf280c303cd8e6b0c54e63eb1164ae43dd6dd66a118c7007feafc7d4a83c",
    "ywc_mgl_debt_selected_current_obligation": "224913258a2b88fd90d1eaee44b26fbe5a19821ee9474e9d7405d87e46ae3c3b",
    "ywc_mgl_debt_current_obligation_ready": "f5b9b595f29719f1f97dbc02b8ad52bcb4ff70f91a6088c85ac928adc952ca53",
    "ywc_mgl_grain_any_affordable_entry_offer": "1cb660e5f28574767cea48611c36e049d99dcda76ccf11af95a029adc2e2d3b3",
    "ywc_mgl_grain_selected_current_obligation": "75e09126159745f4e06b2111f2c79c0ce66485fbdff37cc2d42ddbfe3b2dbcd8",
    "ywc_mgl_grain_current_obligation_ready": "2254e59832c107b3cb52fb3da9db7e38ac41078d0d7fbb599bf3af87e0ee68ab",
}


def _mgl_native_event_digest(event: dict[str, Any]) -> str:
    nodes = parse_block("{ trigger = " + event["trigger"] + " immediate = " + event["immediate"] + " }")
    return hashlib.sha256(repr(tuple(_nqg_node_shape(node) for node in nodes)).encode("utf-8")).hexdigest()


def validate_mgl_native_helper_source(source: str) -> None:
    """Validate all nine authored MGL obligation helper ASTs independent of formatting."""
    if type(source) is not str:
        raise ValueError("MGL scripted-trigger source must be text")
    nodes = parse_block("{\n" + source.lstrip("\ufeff") + "\n}")
    found: dict[str, Node] = {}
    for node in nodes:
        if node.key not in _MGL_HELPER_AST_SHA256:
            continue
        if node.key in found or node.op != "=":
            raise ValueError(f"duplicate or invalid MGL native helper {node.key}")
        found[node.key] = node
    if set(found) != set(_MGL_HELPER_AST_SHA256):
        raise ValueError("MGL source must define all nine native obligation helpers exactly once")
    for name, expected in _MGL_HELPER_AST_SHA256.items():
        digest = hashlib.sha256(json.dumps(_nqg_node_shape(found[name]), separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()
        if digest != expected:
            raise ValueError(f"{name}: full native helper AST drift")


def _validate_mgl_inline_catalog(catalog: dict[str, Any]) -> None:
    expected_arcs = {"v03_mgl_two_trade_roads", "v03_mgl_pastoral_debt", "v03_mgl_princes_monasteries"}
    arcs = [arc for arc in catalog.get("arcs", []) if isinstance(arc, dict) and arc.get("era") == "foundation"]
    if catalog.get("key") != "country_mgl" or len(arcs) != 3 or {arc.get("slug") for arc in arcs} != expected_arcs:
        raise ValueError("MGL inline adapter requires exactly its three foundation arcs")
    witnesses: set[str] = set()
    event_ids: set[str] = set()
    event_count = 0
    total_branches = 0
    for arc in arcs:
        adapter = arc.get("inline_delivery_adapter")
        if not isinstance(adapter, dict) or set(adapter) != {"schema", "live_phases", "branches", "direct_adds"} or adapter.get("schema") != "v03.foundation_inline_adapter.v2":
            raise ValueError(f"{arc['slug']}: MGL requires strict v2 inline metadata")
        journals = arc.get("journals")
        if not isinstance(journals, list) or len(journals) != 2:
            raise ValueError(f"{arc['slug']}: exactly two native JEs are required")
        phases = adapter.get("live_phases")
        if not isinstance(phases, list) or len(phases) != len(journals):
            raise ValueError(f"{arc['slug']}: every native JE needs a live phase")
        actual: list[tuple[str, dict[str, Any]]] = []
        for phase, journal in zip(phases, journals):
            jid = journal.get("id")
            if jid not in _MGL_JOURNAL_SHA256:
                raise ValueError(f"{arc['slug']}: unexpected MGL journal {jid}")
            if not isinstance(phase, dict) or set(phase) != {"journal", "live_witness", "source_script_sha256", "goal_sha256", "exit_sha256"} or phase.get("journal") != jid:
                raise ValueError(f"{arc['slug']}/{jid}: malformed live phase metadata")
            for field, source_key, index in (("source_script_sha256", "script", 0), ("goal_sha256", "goal", 1), ("exit_sha256", "exit_conditions", 2)):
                value = journal.get(source_key)
                if type(value) is not str or hashlib.sha256(value.encode("utf-8")).hexdigest() != _MGL_JOURNAL_SHA256[jid][index] or phase.get(field) != _MGL_JOURNAL_SHA256[jid][index]:
                    raise ValueError(f"{jid}: protected native JE {source_key} drift")
            witness = phase.get("live_witness")
            suffix = jid.removeprefix("ywc_je_v03_mgl_")
            if type(witness) is not str or witness != f"ywc_v03_mgl_inline_live_{suffix}" or witness in witnesses:
                raise ValueError(f"{jid}: invalid or aliased MGL phase witness")
            witnesses.add(witness)
            binding = _mgl_source_binding(jid, journal["script"])
            actual.extend((jid, branch) for branch in binding["branches"])
        recorded = adapter.get("branches")
        if not isinstance(recorded, list) or len(recorded) != len(actual):
            raise ValueError(f"{arc['slug']}: MGL sender branch inventory must be complete")
        for item, (jid, branch) in zip(recorded, actual):
            fields = {"journal", "branch_index", "statement_ordinal", "chain_index", "branch_kind", "event", "branch_sha256", "limit_sha256", "chain_prior", "chain_sha256", "candidates", "queue_exclusions"}
            if not isinstance(item, dict) or set(item) != fields:
                raise ValueError(f"{jid}: malformed MGL source branch binding")
            expected = {"journal": jid, "branch_index": branch["branch_index"], "statement_ordinal": branch["statement_ordinal"], "chain_index": branch["chain_index"], "branch_kind": branch["branch_kind"], "event": branch["event"], "branch_sha256": branch["sha256"], "limit_sha256": branch["limit_sha256"], "chain_prior": branch["chain_prior"], "chain_sha256": branch["chain_sha256"], "candidates": branch["candidates"], "queue_exclusions": branch["queue_exclusions"]}
            if not _mgl_exact_typed_equal(item, expected):
                raise ValueError(f"{jid}: exact MGL branch/chain/queue/auxiliary source binding drift")
            if any(type(item.get(key)) is not int for key in ("branch_index", "statement_ordinal", "chain_index")):
                raise ValueError(f"{jid}: MGL source ordinals must be integers")
            if item["event"] not in {event.get("id") for event in arc.get("events", [])}:
                raise ValueError(f"{jid}: MGL event is not owned by the same arc")
            total_branches += 1
        if len(recorded) != 22:
            raise ValueError(f"{arc['slug']}: each arc must retain its 22 source sender sites")
        if adapter.get("direct_adds") != _kor_direct_adds(arc):
            raise ValueError(f"{arc['slug']}: MGL direct journal-entry source bindings drift")
        for record in adapter["direct_adds"]:
            if record["journal"] not in {journal["id"] for journal in journals}:
                raise ValueError(f"{arc['slug']}: direct-add target is outside the source arc")
        for event in arc.get("events", []):
            event_id = event.get("id")
            if event_id in event_ids:
                raise ValueError(f"{event_id}: duplicate MGL event definition")
            if event_id not in _MGL_EVENT_AST_SHA256 or _mgl_native_event_digest(event) != _MGL_EVENT_AST_SHA256[event_id]:
                raise ValueError(f"{event_id}: full native MGL event trigger/immediate AST drift")
            event_ids.add(event_id)
            event_count += 1
    if total_branches != 66 or event_count != 24 or event_ids != set(_MGL_EVENT_AST_SHA256):
        raise ValueError("MGL native source inventory must contain exactly 66 sender sites and 24 event bodies")


def validate_jhg_native_helper_source(effects_source: str, triggers_source: str) -> None:
    """Validate the locked JHG native helper ABI through its focused adapter."""
    try:
        from tools.v03_jhg_inline_delivery_adapter import validate_jhg_native_helper_source as validate
    except ModuleNotFoundError:
        from v03_jhg_inline_delivery_adapter import validate_jhg_native_helper_source as validate
    validate(effects_source, triggers_source)


def validate_inline_catalog(catalog: dict[str, Any]) -> None:
    """Validate exact inline branch/source ownership for explicitly opted-in arcs."""
    if isinstance(catalog, dict) and catalog.get("key") == "country_tib":
        try:
            from tools.v03_tib_inline_delivery_adapter import validate_tib_inline_catalog
        except ModuleNotFoundError:
            from v03_tib_inline_delivery_adapter import validate_tib_inline_catalog
        return validate_tib_inline_catalog(catalog)
    if isinstance(catalog, dict) and catalog.get("key") == "country_jhg":
        try:
            from tools.v03_jhg_inline_delivery_adapter import validate_jhg_inline_catalog
        except ModuleNotFoundError:
            from v03_jhg_inline_delivery_adapter import validate_jhg_inline_catalog
        validate_jhg_inline_catalog(catalog)
        return
    if isinstance(catalog, dict) and catalog.get("key") == "country_lan":
        _validate_lan_inline_catalog(catalog)
        return
    if isinstance(catalog, dict) and catalog.get("key") == "country_shu":
        _validate_shu_inline_catalog(catalog)
        return
    if isinstance(catalog, dict) and catalog.get("key") == "country_kor":
        _validate_kor_inline_catalog(catalog)
        return
    if isinstance(catalog, dict) and catalog.get("key") == "country_nqg":
        _validate_nqg_inline_catalog(catalog)
        return
    if isinstance(catalog, dict) and catalog.get("key") == "country_nmg":
        _validate_nmg_inline_catalog(catalog)
        return
    if isinstance(catalog, dict) and catalog.get("key") == "country_mgl":
        _validate_mgl_inline_catalog(catalog)
        return
    if not isinstance(catalog, dict) or catalog.get("key") != "country_dmg": raise ValueError("inline adapter is currently enabled only for registered inline countries")
    arcs = catalog.get("arcs")
    if not isinstance(arcs, list): raise ValueError("catalog arcs must be a list")
    expected_slugs = {"v03_dmg_common_subjects", "v03_dmg_two_land_titles", "v03_dmg_court_provinces"}
    active = [arc for arc in arcs if isinstance(arc, dict) and arc.get("era") == "foundation"]
    if {arc.get("slug") for arc in active} != expected_slugs or len(active) != 3: raise ValueError("DMG inline adapter requires exactly its three foundation arcs")
    witnesses: set[str] = set()
    for arc in active:
        adapter = arc.get("inline_delivery_adapter")
        if not isinstance(adapter, dict) or set(adapter) != {"schema", "live_phases", "branches"} or adapter.get("schema") != "v03.foundation_inline_adapter.v1": raise ValueError(f"{arc['slug']}: invalid inline adapter schema")
        journals = arc.get("journals")
        if not isinstance(journals, list) or not journals: raise ValueError(f"{arc['slug']}: journals must be nonempty")
        phases = adapter["live_phases"]
        if not isinstance(phases, list) or len(phases) != len(journals): raise ValueError(f"{arc['slug']}: one witness is required for each source JE")
        for phase, journal in zip(phases, journals):
            if not isinstance(phase, dict) or set(phase) != {"journal", "live_witness", "source_script_sha256", "goal_sha256", "exit_sha256"}: raise ValueError(f"{arc['slug']}: malformed live phase metadata")
            if phase["journal"] != journal.get("id") or not all(type(phase[k]) is str and re.fullmatch(r"[0-9a-f]{64}", phase[k]) for k in ("source_script_sha256", "goal_sha256", "exit_sha256")): raise ValueError(f"{arc['slug']}: source phase binding mismatch")
            if hashlib.sha256(journal["script"].encode("utf-8")).hexdigest() != phase["source_script_sha256"] or hashlib.sha256(journal["goal"].encode("utf-8")).hexdigest() != phase["goal_sha256"] or hashlib.sha256(journal["exit_conditions"].encode("utf-8")).hexdigest() != phase["exit_sha256"]: raise ValueError(f"{arc['slug']}/{journal['id']}: source JE/goal/fail drift")
            witness = phase["live_witness"]
            if type(witness) is not str or not re.fullmatch(r"ywc_v03_dmg_live_[a-z0-9_]+", witness) or witness in witnesses: raise ValueError(f"{arc['slug']}: invalid or duplicate live witness")
            witnesses.add(witness)
        expected = []
        phase_ids = {j["id"] for j in journals}
        for journal in journals:
            for branch in source_binding(journal["id"], journal["script"])["branches"]:
                expected.append((journal["id"], branch))
        recorded = adapter["branches"]
        if not isinstance(recorded, list) or len(recorded) != len(expected): raise ValueError(f"{arc['slug']}: source branch inventory mismatch")
        for item, (jid, branch) in zip(recorded, expected):
            if not isinstance(item, dict) or set(item) != {"journal", "branch_index", "event", "branch_sha256", "limit_sha256", "candidates"}: raise ValueError(f"{arc['slug']}: malformed branch binding")
            if item["journal"] != jid or type(item["branch_index"]) is not int or item["branch_index"] != branch["branch_index"] or item["event"] != branch["event"] or item["branch_sha256"] != branch["sha256"] or item["limit_sha256"] != branch["limit_sha256"]: raise ValueError(f"{arc['slug']}/{jid}: exact source branch drift")
            if item["event"] not in {e["id"] for e in arc["events"]}: raise ValueError(f"{arc['slug']}: branch event is not arc-owned")
            actual = queue_candidates(branch["limit_source"])
            candidates = item["candidates"]
            if not isinstance(candidates, list) or len(candidates) != len(actual): raise ValueError(f"{arc['slug']}/{jid}: source queue candidate mismatch")
            for candidate, source_candidate in zip(candidates, actual):
                expected_fields = {"queue", "kind", "mode"} | ({"value"} if source_candidate["mode"] == "exact" else set())
                if not isinstance(candidate, dict) or set(candidate) != expected_fields or candidate != source_candidate: raise ValueError(f"{arc['slug']}/{jid}: candidate does not match source queue semantics")


def _validate_nmg_inline_catalog(catalog: dict[str, Any]) -> None:
    expected = {"v03_nmg_land_arbitration", "v03_nmg_bilingual_office", "v03_nmg_autonomy_revenue"}
    arcs = [a for a in catalog.get("arcs", []) if isinstance(a, dict) and a.get("era") == "foundation"]
    if len(arcs) != 3 or {a.get("slug") for a in arcs} != expected:
        raise ValueError("NMG inline adapter requires its three foundation arcs and six native JEs")
    witnesses = set()
    total = 0
    owner_for = {"v03_nmg_land_arbitration": "land", "v03_nmg_bilingual_office": "office", "v03_nmg_autonomy_revenue": "revenue"}
    for arc in arcs:
        ad = arc.get("inline_delivery_adapter")
        if not isinstance(ad, dict) or set(ad) != {"schema", "live_phases", "branches", "direct_adds"} or ad.get("schema") != "v03.foundation_inline_adapter.v2":
            raise ValueError(f"{arc['slug']}: NMG requires strict v2 source metadata")
        journals = arc.get("journals")
        if not isinstance(journals, list) or not journals: raise ValueError(f"{arc['slug']}: source journals required")
        phases = ad.get("live_phases")
        if not isinstance(phases, list) or len(phases) != len(journals): raise ValueError(f"{arc['slug']}: every JE needs a live phase")
        for phase, journal in zip(phases, journals):
            if not isinstance(phase, dict) or set(phase) != {"journal", "live_witness", "source_script_sha256", "goal_sha256", "exit_sha256"} or phase.get("journal") != journal.get("id"):
                raise ValueError(f"{arc['slug']}: malformed phase binding")
            for field, src in (("source_script_sha256", "script"), ("goal_sha256", "goal"), ("exit_sha256", "exit_conditions")):
                if phase.get(field) != hashlib.sha256(journal[src].encode()).hexdigest(): raise ValueError(f"{journal['id']}: {src} source drift")
            witness = phase.get("live_witness")
            if not isinstance(witness, str) or not re.fullmatch(r"ywc_v03_nmg_inline_live_[a-z0-9_]+", witness) or witness in witnesses:
                raise ValueError(f"{journal['id']}: invalid or aliased live witness")
            witnesses.add(witness)
        actual = []
        for journal in journals:
            actual.extend((journal["id"], row) for row in _nmg_source_binding(journal["id"], journal["script"])["branches"])
        records = ad.get("branches")
        if not isinstance(records, list) or len(records) != len(actual): raise ValueError(f"{arc['slug']}: sender source inventory mismatch")
        event_ids = {e["id"] for e in arc["events"]}
        for proof, (jid, src) in zip(records, actual):
            required = {"journal", "branch_index", "statement_ordinal", "chain_index", "branch_kind", "event", "branch_sha256", "limit_sha256", "chain_prior", "chain_sha256", "candidates", "queue_exclusions"}
            if not isinstance(proof, dict) or set(proof) != required: raise ValueError(f"{jid}: malformed NMG branch metadata")
            mapping = {"journal": jid, "branch_index": src["branch_index"], "statement_ordinal": src["statement_ordinal"], "chain_index": src["chain_index"], "branch_kind": src["branch_kind"], "event": src["event"], "branch_sha256": src["sha256"], "limit_sha256": src["limit_sha256"], "chain_prior": src["chain_prior"], "chain_sha256": src["chain_sha256"], "candidates": src["candidates"], "queue_exclusions": src["queue_exclusions"]}
            if proof != mapping: raise ValueError(f"{jid}: NMG source branch/chain binding drift")
            if proof["event"] not in event_ids: raise ValueError(f"{jid}: event not owned by source arc")
            journal = next(j for j in journals if j["id"] == jid)
            branch_node = next(n for n in _walk(parse_block(journal["script"])) if n.start == src["start"] and n.end == src["end"])
            queue = proof["candidates"][0]["queue"]
            removals = [n for n in children(branch_node) if n.key == "remove_variable"]
            matching = [n for n in removals if n.value == queue]
            triggers = [n for n in children(branch_node) if n.key == "trigger_event"]
            if len(matching) != 1 or matching[0].op != "=" or not isinstance(matching[0].value, str) or len(triggers) != 1 or matching[0].start >= triggers[0].start:
                raise ValueError(f"{jid}: selected queue must be removed exactly once as a literal before its source trigger")
            if proof["candidates"][0]["queue"] != f"ywc_nmg_{owner_for[arc['slug']]}_{'notice_pending' if proof['candidates'][0]['kind'] == 'notice' else 'pending'}":
                raise ValueError(f"{jid}: queue owner or class mismatch")
            if proof["candidates"][0]["value"] != int(proof["event"].rsplit(".", 1)[1]): raise ValueError(f"{jid}: queue value does not select source event")
            event = next(e for e in arc["events"] if e["id"] == proof["event"])
            _validate_nmg_native_event(event, owner_for[arc["slug"]])
            total += 1
        if ad["direct_adds"] != _kor_direct_adds(arc): raise ValueError(f"{arc['slug']}: direct-add source binding drift")
    if total != 36: raise ValueError("NMG source binding must cover exactly 36 sender branches")


def _validate_nmg_native_event(event: dict[str, Any], owner: str) -> None:
    number = int(event["id"].rsplit(".", 1)[1])
    last = f"ywc_nmg_{owner}_last_event"
    notice = {1006: 12, 1007: 36, 1014: 12, 1015: 36, 1028: 12, 1029: 36}.get(number)
    expected = "ywc_v03_mark_major_delivered = yes "
    if notice is not None:
        due = f"ywc_nmg_{owner}_notice{notice}_due"
        delivered = f"ywc_nmg_{owner}_notice{notice}_delivered"
        expected += (
            f"set_variable = {{ name = ywc_nmg_{owner}_notice_return_event value = var:{last} }} "
            f"set_variable = {{ name = {last} value = {number} }} "
            f"if = {{ limit = {{ has_variable = {due} }} "
            f"set_variable = {{ name = ywc_nmg_{owner}_notice_response_context value = 1 }} "
            f"set_variable = {{ name = {delivered} value = 1 }} remove_variable = {due} }}"
        )
    else:
        expected += f"set_variable = {{ name = {last} value = {number} }}"
    actual_nodes = parse_block(event["immediate"])
    expected_nodes = parse_block("{ " + expected + " }")
    if tuple(_nqg_node_shape(node) for node in actual_nodes) != tuple(_nqg_node_shape(node) for node in expected_nodes):
        raise ValueError(f"{event['id']}: native immediate does not match the complete supported NMG event ABI")


def _nmg_native_receipt(event: dict[str, Any], owner: str) -> tuple[str, int]:
    """Return NMG's one supported last_event receipt from its validated AST."""
    _validate_nmg_native_event(event, owner)
    target = f"ywc_nmg_{owner}_last_event"
    writes = []
    for node in _walk(parse_block(event["immediate"])):
        if node.key != "set_variable" or node.op != "=" or not isinstance(node.value, tuple):
            continue
        names = direct_values(children(node), "name")
        values = direct_values(children(node), "value")
        if len(names) == 1 and names[0].op == "=" and names[0].value == target:
            if len(values) != 1 or values[0].op != "=" or not isinstance(values[0].value, str) or not values[0].value.isdigit():
                raise ValueError(f"{event['id']}: unsupported NMG native receipt value")
            writes.append(int(values[0].value))
    if len(writes) != 1:
        raise ValueError(f"{event['id']}: NMG native receipt target must be written exactly once")
    return target, writes[0]


def validate_nmg_native_helper_source(source: str) -> None:
    """Bind NMG delivery to the complete shared 90-day native cooldown helper."""
    source = source.lstrip("\ufeff")
    nodes = parse_block("{\n" + source + "\n}")
    matches = [n for n in nodes if n.key == "ywc_v03_mark_major_delivered"]
    if len(matches) != 1 or matches[0].op != "=":
        raise ValueError("NMG requires one complete shared ywc_v03_mark_major_delivered definition")
    expected = parse_block("{ ywc_v03_mark_major_delivered = { if = { limit = { NOT = { has_variable = ywc_v03_major_event_cooldown } } set_variable = { name = ywc_v03_major_event_cooldown value = 1 days = 90 } } } }")[0]
    if _nqg_node_shape(matches[0]) != _nqg_node_shape(expected):
        raise ValueError("NMG shared native cooldown helper must preserve the exact 90-day set-once effect")


def _validate_kor_inline_catalog(catalog: dict[str, Any]) -> None:
    if catalog.get("key") != "country_kor" or not isinstance(catalog.get("arcs"), list):
        raise ValueError("KOR inline adapter requires the KOR catalog")
    expected_slugs = {"v03_kor_military_accounts", "v03_kor_school_factions", "v03_kor_controlled_ports"}
    active = [arc for arc in catalog["arcs"] if isinstance(arc, dict) and arc.get("era") == "foundation"]
    if len(active) != 3 or {arc.get("slug") for arc in active} != expected_slugs:
        raise ValueError("KOR v2 inline adapter requires exactly the three foundation arcs")
    all_witnesses: set[str] = set()
    for arc in active:
        adapter = arc.get("inline_delivery_adapter")
        if not isinstance(adapter, dict) or set(adapter) != {"schema", "live_phases", "branches", "direct_adds"} or adapter.get("schema") != "v03.foundation_inline_adapter.v2":
            raise ValueError(f"{arc['slug']}: KOR requires the v2 inline adapter schema")
        journals = arc.get("journals")
        if not isinstance(journals, list) or not journals:
            raise ValueError(f"{arc['slug']}: source journals are required")
        phases = adapter.get("live_phases")
        if not isinstance(phases, list) or len(phases) != len(journals):
            raise ValueError(f"{arc['slug']}: every native JE needs its own live phase witness")
        for phase, journal in zip(phases, journals):
            if not isinstance(phase, dict) or set(phase) != {"journal", "live_witness", "source_script_sha256", "goal_sha256", "exit_sha256"} or phase.get("journal") != journal.get("id"):
                raise ValueError(f"{arc['slug']}: malformed live phase binding")
            for field, source_key in (("source_script_sha256", "script"), ("goal_sha256", "goal"), ("exit_sha256", "exit_conditions")):
                expected = hashlib.sha256(journal[source_key].encode("utf-8")).hexdigest()
                if phase.get(field) != expected:
                    raise ValueError(f"{arc['slug']}/{journal['id']}: source {source_key} drift")
            witness = phase.get("live_witness")
            if not isinstance(witness, str) or not re.fullmatch(r"ywc_v03_kor_inline_live_[a-z0-9_]+", witness) or witness in all_witnesses:
                raise ValueError(f"{arc['slug']}/{journal['id']}: invalid live witness name")
            all_witnesses.add(witness)
        actual: list[tuple[str, dict[str, Any]]] = []
        for journal in journals:
            actual.extend((journal["id"], row) for row in _kor_source_binding(journal["id"], journal["script"])["branches"])
        records = adapter.get("branches")
        if not isinstance(records, list) or len(records) != len(actual):
            raise ValueError(f"{arc['slug']}: every native sender site, including redundant else_if, must be recorded")
        for proof, (jid, source) in zip(records, actual):
            required = {"journal", "branch_index", "statement_ordinal", "chain_index", "branch_kind", "event", "branch_sha256", "limit_sha256", "chain_prior", "chain_sha256", "candidates", "queue_exclusions"}
            if not isinstance(proof, dict) or set(proof) != required:
                raise ValueError(f"{arc['slug']}/{jid}: malformed sender site record")
            if any(type(proof.get(key)) is not int for key in ("branch_index", "statement_ordinal", "chain_index")):
                raise ValueError(f"{arc['slug']}/{jid}: sender ordinals must be integers")
            for key, expected in (("journal", jid), ("branch_index", source["branch_index"]), ("statement_ordinal", source["statement_ordinal"]), ("chain_index", source["chain_index"]), ("branch_kind", source["branch_kind"]), ("event", source["event"]), ("branch_sha256", source["sha256"]), ("limit_sha256", source["limit_sha256"]), ("chain_prior", source["chain_prior"]), ("chain_sha256", source["chain_sha256"]), ("queue_exclusions", source["queue_exclusions"])):
                if proof.get(key) != expected:
                    raise ValueError(f"{arc['slug']}/{jid}: sender chain/source site drift at {key}")
            event_ids = {event["id"] for event in arc["events"]}
            if proof["event"] not in event_ids:
                raise ValueError(f"{arc['slug']}/{jid}: source event is not arc-owned")
            event = next(event for event in arc["events"] if event["id"] == proof["event"])
            if event.get("hidden") is True or proof["event"] in {"ywc_kor.1030", "ywc_kor.1032"}:
                raise ValueError(f"{arc['slug']}/{jid}: hidden/foreign event cannot enter the KOR inline scheduler")
            candidates = proof.get("candidates")
            if not isinstance(candidates, list) or len(candidates) != len(source["candidates"]):
                raise ValueError(f"{arc['slug']}/{jid}: queue candidate inventory drift")
            for candidate, expected_candidate in zip(candidates, source["candidates"]):
                allowed = {"queue", "kind", "mode"} | ({"value"} if expected_candidate["mode"] == "exact" else set())
                if not isinstance(candidate, dict) or set(candidate) != allowed or candidate != expected_candidate:
                    raise ValueError(f"{arc['slug']}/{jid}: queue semantics do not match positive source predicates")
                if "value" in candidate and type(candidate["value"]) is not int:
                    raise ValueError(f"{arc['slug']}/{jid}: queue value must be an integer")
                if proof["event"] == "ywc_kor.1031" and candidate != {"queue": "ywc_kor_instructor_notice_event", "kind": "notice", "mode": "exact", "value": 1031}:
                    raise ValueError("KOR 1031 requires the exact instructor notice queue")
                if proof["event"] == "ywc_kor.1034" and candidate != {"queue": "ywc_kor_procurement_notice_event", "kind": "notice", "mode": "exact", "value": 1034}:
                    raise ValueError("KOR 1034 requires the exact procurement notice queue")
            for prior in proof["chain_prior"]:
                if not isinstance(prior, dict) or set(prior) != {"ordinal", "sha256", "limit_sha256", "limit_source"} or type(prior.get("ordinal")) is not int or not isinstance(prior.get("limit_source"), str):
                    raise ValueError(f"{arc['slug']}/{jid}: invalid prior predicate record")
                if any(not isinstance(prior.get(key), str) or not re.fullmatch(r"[0-9a-f]{64}", prior[key]) for key in ("sha256", "limit_sha256")):
                    raise ValueError(f"{arc['slug']}/{jid}: invalid prior predicate hash")
            if not isinstance(proof.get("chain_sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", proof["chain_sha256"]):
                raise ValueError(f"{arc['slug']}/{jid}: queue semantics do not match positive source predicates")
        direct_adds = adapter.get("direct_adds")
        if not isinstance(direct_adds, list):
            raise ValueError(f"{arc['slug']}: source direct-add callers drift or are incomplete")
        for record in direct_adds:
            if not isinstance(record, dict) or set(record) != {"event", "option", "journal", "site_ordinal", "effect_sha256", "site_sha256"}:
                raise ValueError(f"{arc['slug']}: malformed direct-add source binding")
            if type(record.get("site_ordinal")) is not int:
                raise ValueError(f"{arc['slug']}: direct-add ordinal must be an integer")
            if any(type(record.get(field)) is not str for field in ("event", "option", "journal", "effect_sha256", "site_sha256")):
                raise ValueError(f"{arc['slug']}: direct-add source fields must be strings")
            if any(not re.fullmatch(r"[0-9a-f]{64}", record[field]) for field in ("effect_sha256", "site_sha256")):
                raise ValueError(f"{arc['slug']}: direct-add source hashes are malformed")
        if direct_adds != _kor_direct_adds(arc):
            raise ValueError(f"{arc['slug']}: source direct-add callers drift or are incomplete")
        for record in direct_adds:
            target = next((journal for journal in arc["journals"] if journal["id"] == record["journal"]), None)
            if target is None:
                raise ValueError(f"{arc['slug']}: direct-add target must be owned by its source arc")


def _validate_nqg_inline_catalog(catalog: dict[str, Any]) -> None:
    """Strictly validate NQG's native source chains and four late-event classes."""
    expected_slugs = {"v03_nqg_winter_court", "v03_nqg_hunting_rights", "v03_nqg_northern_port"}
    arc_bases = {"v03_nqg_winter_court": "winter", "v03_nqg_hunting_rights": "hunting", "v03_nqg_northern_port": "port"}
    late_events = {"v03_nqg_winter_court": "ywc_nqg.1009", "v03_nqg_hunting_rights": "ywc_nqg.1015", "v03_nqg_northern_port": "ywc_nqg.1027"}
    active = [arc for arc in catalog.get("arcs", []) if isinstance(arc, dict) and arc.get("era") == "foundation"]
    if len(active) != 3 or {arc.get("slug") for arc in active} != expected_slugs:
        raise ValueError("NQG inline adapter requires exactly its three foundation arcs")
    witnesses: set[str] = set()
    queues_by_owner: dict[str, str] = {}
    for arc in active:
        adapter = arc.get("inline_delivery_adapter")
        if not isinstance(adapter, dict) or set(adapter) != {"schema", "live_phases", "branches", "direct_adds"} or adapter.get("schema") != "v03.foundation_inline_adapter.v2":
            raise ValueError(f"{arc['slug']}: NQG requires strict v2 inline metadata")
        journals = arc.get("journals")
        if not isinstance(journals, list) or not journals:
            raise ValueError(f"{arc['slug']}: source journals are required")
        phases = adapter["live_phases"]
        if not isinstance(phases, list) or len(phases) != len(journals):
            raise ValueError(f"{arc['slug']}: every native JE needs its own live phase witness")
        for phase, journal in zip(phases, journals):
            if not isinstance(phase, dict) or set(phase) != {"journal", "live_witness", "source_script_sha256", "goal_sha256", "exit_sha256"} or phase.get("journal") != journal.get("id"):
                raise ValueError(f"{arc['slug']}: malformed live phase binding")
            for field, source_key in (("source_script_sha256", "script"), ("goal_sha256", "goal"), ("exit_sha256", "exit_conditions")):
                if phase.get(field) != hashlib.sha256(journal[source_key].encode("utf-8")).hexdigest():
                    raise ValueError(f"{arc['slug']}/{journal['id']}: source {source_key} drift")
            witness = phase.get("live_witness")
            if type(witness) is not str or not re.fullmatch(r"ywc_v03_nqg_inline_live_[a-z0-9_]+", witness) or witness in witnesses:
                raise ValueError(f"{arc['slug']}/{journal['id']}: invalid or duplicate live witness")
            witnesses.add(witness)
        actual: list[tuple[str, dict[str, Any]]] = []
        journal_by_id = {journal["id"]: journal for journal in journals}
        for journal in journals:
            actual.extend((journal["id"], row) for row in _kor_source_binding(journal["id"], journal["script"]) ["branches"])
        records = adapter["branches"]
        if not isinstance(records, list) or len(records) != len(actual):
            raise ValueError(f"{arc['slug']}: every native sender site must be recorded")
        event_ids = {event["id"] for event in arc["events"]}
        for proof, (jid, source) in zip(records, actual):
            required = {"journal", "branch_index", "statement_ordinal", "chain_index", "branch_kind", "event", "branch_sha256", "limit_sha256", "chain_prior", "chain_sha256", "candidates", "queue_exclusions"}
            if not isinstance(proof, dict) or set(proof) != required:
                raise ValueError(f"{arc['slug']}/{jid}: malformed source sender metadata")
            for key in ("branch_index", "statement_ordinal", "chain_index"):
                if type(proof.get(key)) is not int:
                    raise ValueError(f"{arc['slug']}/{jid}: {key} must be an integer")
            for key in ("journal", "branch_index", "statement_ordinal", "chain_index", "branch_kind", "event", "branch_sha256", "limit_sha256", "chain_prior", "chain_sha256", "queue_exclusions"):
                expected = jid if key == "journal" else source[key if key not in {"branch_sha256", "limit_sha256"} else ("sha256" if key == "branch_sha256" else "limit_sha256")]
                if proof.get(key) != expected:
                    raise ValueError(f"{arc['slug']}/{jid}: exact source chain/site drift at {key}")
            if proof["event"] not in event_ids:
                raise ValueError(f"{arc['slug']}/{jid}: sender event is not arc-owned")
            expected_candidates = source["candidates"]
            if not isinstance(proof["candidates"], list) or proof["candidates"] != expected_candidates:
                raise ValueError(f"{arc['slug']}/{jid}: candidate class/value differs from native source")
            base = arc_bases[arc["slug"]]
            journal_source = journal_by_id[jid]["script"]
            branch_source = journal_source[source["start"]:source["end"]]
            branch_node = parse_block("{ " + branch_source + " }")[0]
            direct_triggers = direct_values(children(branch_node), "trigger_event")
            aid_notice = arc["slug"] == "v03_nqg_winter_court" and source["event"] == "ywc_nqg.1031"
            if len(direct_triggers) != 1 or source["event"] != late_events[arc["slug"]] and not aid_notice and any(candidate["kind"] != "normal_queued_event" for candidate in expected_candidates):
                raise ValueError(f"{arc['slug']}/{jid}: late delivery classes must target their native late event")
            setters: dict[str, list[Node]] = {}
            for node in children(branch_node):
                if node.key != "set_variable" or not isinstance(node.value, tuple):
                    continue
                names = direct_values(children(node), "name")
                values = direct_values(children(node), "value")
                if len(names) == 1 and names[0].op == "=" and isinstance(names[0].value, str) and "_notice" in names[0].value and names[0].value.endswith("_intent"):
                    setters.setdefault(names[0].value, []).append(node)
                    if node.op != "=" or len(values) != 1 or values[0].op != "=" or values[0].value != "1" or node.start >= direct_triggers[0].start:
                        raise ValueError(f"{arc['slug']}/{jid}: notice intent must be set to 1 before native trigger_event")
            expected_intents: set[str] = set()
            for candidate in proof["candidates"]:
                allowed = {"queue", "kind", "mode"} | ({"value"} if candidate.get("mode") == "exact" else set())
                if not isinstance(candidate, dict) or set(candidate) != allowed or candidate.get("kind") not in {"normal_queued_event", "notice12", "notice36", "remedy_final", "notice"}:
                    raise ValueError(f"{arc['slug']}/{jid}: malformed candidate class")
                if any(type(candidate.get(field)) is not str for field in ("queue", "kind", "mode")):
                    raise ValueError(f"{arc['slug']}/{jid}: candidate fields must be strings")
                if "value" in candidate and type(candidate["value"]) is not int:
                    raise ValueError(f"{arc['slug']}/{jid}: exact queue value must be an integer")
                expected_suffix = {"normal_queued_event": "pending", "notice12": "notice12_pending", "notice36": "notice36_pending", "remedy_final": "remedy_final_pending", "notice": "aid_notice_event"}[candidate["kind"]]
                if candidate["queue"] != f"ywc_nqg_{base}_{expected_suffix}":
                    raise ValueError(f"{arc['slug']}/{jid}: candidate queue is not owned by its arc and class")
                if candidate["kind"] == "notice":
                    if not aid_notice or candidate != {"queue": "ywc_nqg_winter_aid_notice_event", "kind": "notice", "mode": "exact", "value": 1031}:
                        raise ValueError(f"{arc['slug']}/{jid}: invalid NQG aid notice candidate")
                elif candidate["kind"] == "normal_queued_event":
                    event_number = source["event"].rsplit(".", 1)[-1]
                    if candidate["mode"] != "exact" or type(candidate.get("value")) is not int or not event_number.isdigit() or candidate["value"] != int(event_number):
                        raise ValueError(f"{arc['slug']}/{jid}: normal queue must carry its exact native event id")
                elif candidate["mode"] != "presence" or "value" in candidate:
                    raise ValueError(f"{arc['slug']}/{jid}: notice and remedy queues must use native presence semantics")
                if candidate["kind"] in {"notice12", "notice36"}:
                    intent = f"ywc_nqg_{base}_{candidate['kind']}_intent"
                    expected_intents.add(intent)
                    if source["event"] != late_events[arc["slug"]] or len(setters.get(intent, [])) != 1:
                        raise ValueError(f"{arc['slug']}/{jid}: notice sender must set its own class intent at the native late event")
                owner = queues_by_owner.setdefault(candidate["queue"], arc["slug"])
                if owner != arc["slug"]:
                    raise ValueError(f"NQG source queue alias crosses arcs: {candidate['queue']}")
            if set(setters) != expected_intents:
                raise ValueError(f"{arc['slug']}/{jid}: sender intent setters do not match its native notice candidates")
            for prior in proof["chain_prior"]:
                if not isinstance(prior, dict) or set(prior) != {"ordinal", "sha256", "limit_sha256", "limit_source"}:
                    raise ValueError(f"{arc['slug']}/{jid}: malformed source chain predicate")
                if type(prior["ordinal"]) is not int or type(prior["limit_source"]) is not str:
                    raise ValueError(f"{arc['slug']}/{jid}: source chain predicate types are invalid")
                if any(type(prior[field]) is not str or re.fullmatch(r"[0-9a-f]{64}", prior[field]) is None for field in ("sha256", "limit_sha256")):
                    raise ValueError(f"{arc['slug']}/{jid}: source chain hashes are malformed")
        direct_adds = adapter["direct_adds"]
        if not isinstance(direct_adds, list) or direct_adds != _kor_direct_adds(arc):
            raise ValueError(f"{arc['slug']}: direct-add caller inventory drift")
        for record in direct_adds:
            if not isinstance(record, dict) or set(record) != {"event", "option", "journal", "site_ordinal", "effect_sha256", "site_sha256"}:
                raise ValueError(f"{arc['slug']}: malformed direct-add record")
            if type(record["site_ordinal"]) is not int or any(type(record[field]) is not str for field in ("event", "option", "journal", "effect_sha256", "site_sha256")):
                raise ValueError(f"{arc['slug']}: direct-add record types are invalid")
            if any(re.fullmatch(r"[0-9a-f]{64}", record[field]) is None for field in ("effect_sha256", "site_sha256")):
                raise ValueError(f"{arc['slug']}: direct-add hashes are malformed")
        if any(record["journal"] not in {journal["id"] for journal in journals} for record in direct_adds):
            raise ValueError(f"{arc['slug']}: direct-add target is outside its source arc")


def _nqg_node_shape(node: Node) -> tuple[Any, ...]:
    value = tuple(_nqg_node_shape(child) for child in node.value) if isinstance(node.value, tuple) else node.value
    return node.key, node.op, value


def validate_nqg_native_helper_source(catalog: dict[str, Any], effects_source: str) -> None:
    """Prove each late notice callback's native intent/receipt/open mapping."""
    if type(effects_source) is not str:
        raise ValueError("NQG native effects source must be text")
    nodes = parse_block("{\n" + effects_source + "\n}")
    late_events = {"v03_nqg_winter_court": ("winter", "ywc_nqg.1009"),
                   "v03_nqg_hunting_rights": ("hunting", "ywc_nqg.1015"),
                   "v03_nqg_northern_port": ("port", "ywc_nqg.1027")}
    for slug, (base, event_id) in late_events.items():
        helper = f"ywc_nqg_{base}_mark_notice_delivery"
        matching_definitions = [node for node in nodes if node.key == helper]
        if len(matching_definitions) != 1 or matching_definitions[0].op != "=" or not isinstance(matching_definitions[0].value, tuple):
            raise ValueError(f"NQG native helper is missing: {helper}")
        prefix = f"ywc_nqg_{base}"
        expected_source = (
            "{ if = { limit = { has_variable = " + prefix + "_notice12_intent } "
            "remove_variable = " + prefix + "_notice12_intent "
            "set_variable = { name = " + prefix + "_notice12_open value = 1 } "
            "set_variable = { name = " + prefix + "_blocked_12_delivered value = 1 } } "
            "else_if = { limit = { has_variable = " + prefix + "_notice36_intent } "
            "remove_variable = " + prefix + "_notice36_intent "
            "set_variable = { name = " + prefix + "_notice36_open value = 1 } "
            "set_variable = { name = " + prefix + "_blocked_36_delivered value = 1 } } }"
        )
        expected = parse_block("{ " + helper + " = " + expected_source + " }")[0]
        if _nqg_node_shape(matching_definitions[0]) != _nqg_node_shape(expected):
            raise ValueError(f"NQG native notice intent/receipt/open mapping drift: {helper}")
        arcs = [arc for arc in catalog.get("arcs", []) if isinstance(arc, dict) and arc.get("slug") == slug]
        if len(arcs) != 1:
            raise ValueError(f"NQG late-event arc is missing or ambiguous: {slug}")
        events = [event for event in arcs[0].get("events", []) if isinstance(event, dict) and event.get("id") == event_id]
        if len(events) != 1 or type(events[0].get("immediate")) is not str:
            raise ValueError(f"NQG native late event is missing: {event_id}")
        immediate = parse_block(events[0]["immediate"])
        expected_immediate = parse_block("{ ywc_v03_mark_major_delivered = yes " + helper + " = yes }")
        actual_shape = tuple(_nqg_node_shape(node) for node in immediate)
        expected_shape = tuple(_nqg_node_shape(node) for node in expected_immediate)
        if actual_shape != expected_shape:
            raise ValueError(f"NQG late-event immediate must contain only mark-major then its own direct notice helper: {event_id}")

def _inner_text(block: str) -> str:
    value = block.strip()
    if len(value) < 2 or value[0] != "{" or value[-1] != "}": raise ValueError("expected a braced source block")
    parse_block(value)
    return value[1:-1].strip()


def _limit_inner_source(statement: str) -> str:
    source = "{ " + statement + " }"
    nodes = parse_block(source)
    if len(nodes) != 1 or nodes[0].key != "limit" or not isinstance(nodes[0].value, tuple):
        raise ValueError("expected one source limit block")
    return source[nodes[0].value_start + 1:nodes[0].value_end - 1].strip()


def _script_var(name: str) -> str:
    if not re.fullmatch(r"[a-z][a-z0-9_]*", name): raise ValueError(f"unsafe generated variable: {name}")
    return name


def _queue_snapshot_name(candidate_id: int, queue: str, suffix: str, prefix: str = "ywc_v03_dmg_inline") -> str:
    queue_id = re.sub(r"[^a-z0-9_]", "_", queue.removeprefix("ywc_dmg_").removeprefix("ywc_kor_").removeprefix("ywc_nqg_").removeprefix("ywc_shu_"))
    return _script_var(f"{prefix}_c{candidate_id}_{queue_id}_{suffix}")


def _kor_instructor_fields(candidate_id: int) -> dict[str, str]:
    stem = f"ywc_v03_kor_inline_c{candidate_id}_instructor_"
    return {name: stem + name for name in ("serial", "generation", "request_state", "reason",
                                          "partner_available", "partner", "body_completed",
                                          "body_completed_epoch", "body_completed_serial")}


def _kor_instructor_checks(candidate_id: int, *, delivered: bool) -> list[str]:
    """Pre-export checks use live/reserved state; delivered checks require C-fields."""
    f = _kor_instructor_fields(candidate_id)
    checks = ["ywc_kor_instructor_notice_live = yes",
              "has_variable = ywc_kor_instructor_generation",
              "has_variable = ywc_kor_instructor_state"]
    live = {"serial": "ywc_kor_instructor_notice_serial",
            "generation": "ywc_kor_instructor_notice_generation",
            "request_state": "ywc_kor_instructor_notice_request_state",
            "reason": "ywc_kor_instructor_notice_reason"}
    for suffix, name in live.items():
        checks += [f"has_variable = {f[suffix]}", f"var:{f[suffix]} = var:{name}"]
    checks += [f"has_variable = {f['partner_available']}",
               f"OR = {{ var:{f['partner_available']} = 0 var:{f['partner_available']} = 1 }}",
               "var:ywc_kor_instructor_notice_generation = var:ywc_kor_instructor_generation",
               "var:ywc_kor_instructor_notice_request_state = var:ywc_kor_instructor_state",
               f"OR = {{ AND = {{ var:{f['partner_available']} = 0 NOT = {{ exists = var:ywc_kor_instructor_notice_partner }} }} "
               f"AND = {{ var:{f['partner_available']} = 1 exists = var:{f['partner']} "
               f"var:{f['partner']} ?= var:ywc_kor_instructor_notice_partner "
               f"var:{f['partner']} = {{ is_country_alive = yes }} }} }}"]
    if delivered:
        captured = "ywc_kor_notice_"
        checks += [f"exists = scope:{captured}owner", f"scope:{captured}owner ?= this",
                   f"scope:{captured}candidate ?= {candidate_id}",
                   "has_variable = ywc_v03_kor_inline_reservation_epoch",
                   "var:ywc_v03_kor_inline_reservation_epoch > 0",
                   f"scope:{captured}epoch ?= var:ywc_v03_kor_inline_reservation_epoch"]
        for suffix in ("serial", "generation", "request_state", "reason", "partner_available"):
            checks.append(f"scope:{captured}{suffix} ?= var:{f[suffix]}")
        checks += [f"OR = {{ AND = {{ var:{f['partner_available']} = 0 NOT = {{ exists = scope:{captured}partner }} }} "
                   f"AND = {{ var:{f['partner_available']} = 1 exists = scope:{captured}partner "
                   f"scope:{captured}partner ?= var:{f['partner']} }} }}"]
    return checks


def _kor_procurement_fields(candidate_id: int) -> dict[str, str]:
    stem = f"ywc_v03_kor_inline_c{candidate_id}_procurement_"
    return {name: stem + name for name in ("serial", "generation", "request_state", "reason",
                                           "partner_available", "partner", "body_completed",
                                           "body_completed_epoch", "body_completed_serial")}


def _kor_procurement_checks(candidate_id: int, *, delivered: bool) -> list[str]:
    """Procurement mirror of the instructor checks: separate queue and fields."""
    f = _kor_procurement_fields(candidate_id)
    checks = ["ywc_kor_procurement_notice_live = yes",
              "has_variable = ywc_kor_procurement_generation",
              "has_variable = ywc_kor_procurement_state"]
    live = {"serial": "ywc_kor_procurement_notice_serial",
            "generation": "ywc_kor_procurement_notice_generation",
            "request_state": "ywc_kor_procurement_notice_request_state",
            "reason": "ywc_kor_procurement_notice_reason"}
    for suffix, name in live.items():
        checks += [f"has_variable = {f[suffix]}", f"var:{f[suffix]} = var:{name}"]
    checks += [f"has_variable = {f['partner_available']}",
               f"OR = {{ var:{f['partner_available']} = 0 var:{f['partner_available']} = 1 }}",
               "var:ywc_kor_procurement_notice_generation = var:ywc_kor_procurement_generation",
               "var:ywc_kor_procurement_notice_request_state = var:ywc_kor_procurement_state",
               f"OR = {{ AND = {{ var:{f['partner_available']} = 0 NOT = {{ exists = var:ywc_kor_procurement_notice_partner }} }} "
               f"AND = {{ var:{f['partner_available']} = 1 exists = var:{f['partner']} "
               f"var:{f['partner']} ?= var:ywc_kor_procurement_notice_partner "
               f"var:{f['partner']} = {{ is_country_alive = yes }} }} }}"]
    if delivered:
        captured = "ywc_kor_procurement_notice_"
        checks += [f"exists = scope:{captured}owner", f"scope:{captured}owner ?= this",
                   f"scope:{captured}candidate ?= {candidate_id}",
                   "has_variable = ywc_v03_kor_inline_reservation_epoch",
                   "var:ywc_v03_kor_inline_reservation_epoch > 0",
                   f"scope:{captured}epoch ?= var:ywc_v03_kor_inline_reservation_epoch"]
        for suffix in ("serial", "generation", "request_state", "reason", "partner_available"):
            checks.append(f"scope:{captured}{suffix} ?= var:{f[suffix]}")
        checks += [f"OR = {{ AND = {{ var:{f['partner_available']} = 0 NOT = {{ exists = scope:{captured}partner }} }} "
                   f"AND = {{ var:{f['partner_available']} = 1 exists = scope:{captured}partner "
                   f"scope:{captured}partner ?= var:{f['partner']} }} }}"]
    return checks


def _nqg_aid_fields(candidate_id: int) -> dict[str, str]:
    stem = f"ywc_v03_nqg_inline_c{candidate_id}_aid_"
    return {name: stem + name for name in ("serial", "generation", "request_state", "reason",
                                           "partner_available", "partner", "body_completed",
                                           "body_completed_epoch", "body_completed_serial")}


def _nqg_aid_checks(candidate_id: int, *, delivered: bool) -> list[str]:
    """NQG aid notice with independent frozen queue and partner identity."""
    f = _nqg_aid_fields(candidate_id)
    checks = ["ywc_nqg_winter_aid_notice_live = yes",
              "has_variable = ywc_nqg_aid_generation",
              "has_variable = ywc_nqg_aid_state"]
    live = {"serial": "ywc_nqg_winter_aid_notice_serial",
            "generation": "ywc_nqg_winter_aid_notice_generation",
            "request_state": "ywc_nqg_winter_aid_notice_request_state",
            "reason": "ywc_nqg_winter_aid_notice_reason"}
    for suffix, name in live.items():
        checks += [f"has_variable = {f[suffix]}", f"var:{f[suffix]} = var:{name}"]
    checks += [f"has_variable = {f['partner_available']}",
               f"OR = {{ var:{f['partner_available']} = 0 var:{f['partner_available']} = 1 }}",
               "var:ywc_nqg_winter_aid_notice_generation = var:ywc_nqg_aid_generation",
               "var:ywc_nqg_winter_aid_notice_request_state = var:ywc_nqg_aid_state",
               f"OR = {{ AND = {{ var:{f['partner_available']} = 0 NOT = {{ exists = var:ywc_nqg_winter_aid_notice_partner }} }} "
               f"AND = {{ var:{f['partner_available']} = 1 exists = var:{f['partner']} "
               f"var:{f['partner']} ?= var:ywc_nqg_winter_aid_notice_partner "
               f"var:{f['partner']} = {{ is_country_alive = yes }} }} }}"]
    if delivered:
        captured = "ywc_nqg_winter_aid_notice_"
        checks += [f"exists = scope:{captured}owner", f"scope:{captured}owner ?= this",
                   f"scope:{captured}candidate ?= {candidate_id}",
                   "has_variable = ywc_v03_nqg_inline_reservation_epoch",
                   "var:ywc_v03_nqg_inline_reservation_epoch > 0",
                   f"scope:{captured}epoch ?= var:ywc_v03_nqg_inline_reservation_epoch"]
        for suffix in ("serial", "generation", "request_state", "reason", "partner_available"):
            checks.append(f"scope:{captured}{suffix} ?= var:{f[suffix]}")
        checks += [f"OR = {{ AND = {{ var:{f['partner_available']} = 0 NOT = {{ exists = scope:{captured}partner }} }} "
                   f"AND = {{ var:{f['partner_available']} = 1 exists = scope:{captured}partner "
                   f"scope:{captured}partner ?= var:{f['partner']} }} }}"]
    return checks


def _branch_node(pulse: str, branch: dict[str, Any]) -> tuple[Node, Node, Node]:
    top = parse_block(pulse)
    monthly = direct_values(top, "on_monthly_pulse")
    effect = direct_values(children(monthly[0]), "effect")
    sender_nodes = []
    if branch.get("branch_kind") and branch.get("start") is not None:
        for node in _walk(children(effect[0])):
            if node.start == branch["start"] and node.end == branch["end"]:
                limits = direct_values(children(node), "limit")
                triggers = direct_values(children(node), "trigger_event")
                if len(limits) == 1 and len(triggers) == 1 and block_digest(node, pulse) == branch["sha256"]:
                    return node, limits[0], triggers[0]
    for node in children(effect[0]):
        if node.key not in {"if", "else_if"}: continue
        if trigger_event_ids((node,)): sender_nodes.append(node)
    if branch["branch_index"] >= len(sender_nodes): raise ValueError("source sender branch index disappeared")
    node = sender_nodes[branch["branch_index"]]
    if block_digest(node, pulse) != branch["sha256"]: raise ValueError("source sender branch hash drift")
    limits = direct_values(children(node), "limit")
    triggers = direct_values(children(node), "trigger_event")
    if len(limits) != 1 or len(triggers) != 1: raise ValueError("sender branch must have one direct limit and one direct event")
    return node, limits[0], triggers[0]


def _nqg_state_variables(arc_slug: str, arc_candidates: list[dict[str, Any]]) -> list[str]:
    arc = {"v03_nqg_winter_court": "winter", "v03_nqg_hunting_rights": "hunting", "v03_nqg_northern_port": "port"}.get(arc_slug)
    if arc is None:
        raise ValueError(f"unknown NQG arc: {arc_slug}")
    base = f"ywc_nqg_{arc}"
    names = {c["queue"]["queue"] for c in arc_candidates}
    if any(c.get("nqg_aid_notice") for c in arc_candidates):
        names.add("ywc_nqg_winter_pending")
    names.update({f"{base}_notice12_intent", f"{base}_notice36_intent",
                  f"{base}_notice12_open", f"{base}_notice36_open",
                  f"{base}_blocked_12_delivered", f"{base}_blocked_36_delivered"})
    return sorted(names)


def _nqg_candidate_state(c: dict[str, Any], candidates: list[dict[str, Any]]) -> list[str]:
    related = [x for x in candidates if x["arc"]["slug"] == c["arc"]["slug"] and x["event"]["id"] == c["event"]["id"]]
    return _nqg_state_variables(c["arc"]["slug"], related)


def _nqg_event_calls_notice_helper(event: dict[str, Any], arc_slug: str) -> bool:
    base = {"v03_nqg_winter_court": "winter", "v03_nqg_hunting_rights": "hunting", "v03_nqg_northern_port": "port"}.get(arc_slug)
    if base is None or type(event.get("immediate")) is not str:
        return False
    helper = f"ywc_nqg_{base}_mark_notice_delivery"
    return any(node.key == helper and node.op == "=" and node.value == "yes" for node in parse_block(event["immediate"]))


def _dmg_native_notice_consumption(c: dict[str, Any]) -> str | None:
    """Return the proven native consumption branch for a DMG blocked notice."""
    queue = c["queue"]["queue"]
    if not queue.endswith(("_blocked_12_notice", "_blocked_36_notice")):
        return None
    helpers = [node.key for node in parse_block(c["event"]["immediate"])
               if node.op == "=" and node.value == "yes"
               and node.key.startswith("ywc_dmg_foundation_mark_")
               and node.key.endswith("_notice_delivered")]
    if len(helpers) != 1:
        return None
    receipt = c.get("receipt_variable")
    receipt_value = c.get("receipt_value")
    if not receipt or type(receipt_value) is not int:
        return None
    marker = queue.replace("_notice", "_delivered")
    return ("AND = { NOT = { has_variable = " + queue + " } "
            f"has_variable = {marker} var:{marker} = 1 "
            f"has_variable = {receipt} var:{receipt} = {receipt_value} }}")


def _nmg_native_postchecks(c: dict[str, Any], prefix: str) -> list[str]:
    if not c.get("native_return"):
        return []
    value = _queue_snapshot_name(c["id"], c["receipt_variable"], "native_value", prefix)
    # The authored native body always writes notice_return_event from last_event.
    # A missing Clausewitz source variable reads as numeric zero, so compare the
    # actual post-body write with the captured numeric snapshot in both cases.
    checks = [f"has_variable = {c['native_return']}",
              f"var:{c['native_return']} = var:{value}"]
    if c.get("native_notice"):
        checks += [f"NOT = {{ has_variable = {c['native_due']} }}",
                   f"has_variable = {c['native_delivered']}", f"var:{c['native_delivered']} = 1",
                   f"has_variable = {c['native_context']}", f"var:{c['native_context']} = 1"]
    return checks


def _mgl_tracked_state(c: dict[str, Any]) -> list[str]:
    stem = {"v03_mgl_two_trade_roads": "roads", "v03_mgl_pastoral_debt": "debt",
            "v03_mgl_princes_monasteries": "grain"}[c["arc"]["slug"]]
    return [f"ywc_mgl_{stem}_pending_event", f"ywc_mgl_{stem}_blocked_12_notice_event",
            f"ywc_mgl_{stem}_blocked_36_notice_event", f"ywc_mgl_{stem}_blocked_notice_last_delivered"]


def _mgl_snapshot_checks(c: dict[str, Any], prefix: str) -> list[str]:
    phase = c["phase"]["live_witness"]
    checks = [f"has_variable = {phase}", f"var:{phase} = 1"]
    ident = c["id"]
    for name in _mgl_tracked_state(c):
        present = _queue_snapshot_name(ident, name, "present", prefix)
        value = _queue_snapshot_name(ident, name, "value", prefix)
        if name == c.get("native_notice_marker"):
            checks += [f"has_variable = {name}", f"var:{name} = {c['native_notice_marker_value']}"]
        else:
            checks.append("OR = { "
                          f"AND = {{ has_variable = {present} has_variable = {value} var:{present} = 1 "
                          f"has_variable = {name} var:{name} = var:{value} }} "
                          f"AND = {{ has_variable = {present} has_variable = {value} var:{present} = 0 "
                          f"var:{value} = 0 NOT = {{ has_variable = {name} }} }} }}")
    return checks


def render_inline_country_adapters(catalog: dict[str, Any]) -> dict[str, Any]:
    """Render source-bound per-branch dispatch gates, snapshots and immediate ACKs."""
    if isinstance(catalog, dict) and catalog.get("key") == "country_tib":
        try:
            from tools.v03_tib_inline_delivery_adapter import render_tib_inline_country_adapters
        except ModuleNotFoundError:
            from v03_tib_inline_delivery_adapter import render_tib_inline_country_adapters
        return render_tib_inline_country_adapters(catalog)
    if isinstance(catalog, dict) and catalog.get("key") == "country_jhg":
        try:
            from tools.v03_jhg_inline_delivery_adapter import render_jhg_inline_country_adapters
        except ModuleNotFoundError:
            from v03_jhg_inline_delivery_adapter import render_jhg_inline_country_adapters
        return render_jhg_inline_country_adapters(catalog)
    validate_inline_catalog(catalog)
    is_kor = catalog["key"] == "country_kor"
    is_nqg = catalog["key"] == "country_nqg"
    is_shu = catalog["key"] == "country_shu"
    is_dmg = catalog["key"] == "country_dmg"
    is_lan = catalog["key"] == "country_lan"
    is_nmg = catalog["key"] == "country_nmg"
    is_mgl = catalog["key"] == "country_mgl"
    is_supported_inline_country = is_dmg or is_kor or is_nqg or is_shu or is_lan or is_nmg or is_mgl
    prefix = "ywc_v03_mgl_inline" if is_mgl else "ywc_v03_nmg_inline" if is_nmg else "ywc_v03_lan_inline" if is_lan else "ywc_v03_shu_inline" if is_shu else "ywc_v03_kor_inline" if is_kor else "ywc_v03_nqg_inline" if is_nqg else "ywc_v03_dmg_inline"
    arcs = _shu_active_arcs(catalog) if is_shu else [arc for arc in catalog["arcs"] if arc.get("era") == "foundation"]
    arc_order = {arc["slug"]: idx for idx, arc in enumerate(arcs)}
    phases: dict[str, dict[str, Any]] = {}
    candidates: list[dict[str, Any]] = []
    source_by_journal: dict[str, dict[str, Any]] = {}
    for arc in arcs:
        ad = arc["inline_delivery_adapter"]
        for phase in ad["live_phases"]:
            journal = next(j for j in arc["journals"] if j["id"] == phase["journal"])
            phases[journal["id"]] = {"arc": arc, "phase": phase, "journal": journal}
            source_by_journal[journal["id"]] = journal
        for proof in ad["branches"]:
            journal = source_by_journal[proof["journal"]]
            binding = _mgl_source_binding(journal["id"], journal["script"]) if is_mgl else _nmg_source_binding(journal["id"], journal["script"]) if is_nmg else _lan_source_binding(journal["id"], journal["script"]) if is_lan else _kor_source_binding(journal["id"], journal["script"], candidate_parser=_shu_queue_candidates) if is_shu else _kor_source_binding(journal["id"], journal["script"]) if (is_kor or is_nqg) else source_binding(journal["id"], journal["script"])
            branch = binding["branches"][proof["branch_index"]]
            for queue in proof["candidates"]:
                event = next(e for e in arc["events"] if e["id"] == proof["event"])
                kor_instructor_notice = is_kor and event["id"] == "ywc_kor.1031"
                kor_procurement_notice = is_kor and event["id"] == "ywc_kor.1034"
                nqg_aid_notice = is_nqg and event["id"] == "ywc_nqg.1031"
                if is_kor and event["id"] in {"ywc_kor.1030", "ywc_kor.1032", "ywc_kor.1033", "ywc_kor.1035"}:
                    raise ValueError("foreign/hidden KOR events cannot be inline candidates")
                if kor_instructor_notice and queue != {"queue": "ywc_kor_instructor_notice_event", "kind": "notice", "mode": "exact", "value": 1031}:
                    raise ValueError("KOR instructor notice candidate has wrong queue shape")
                if kor_procurement_notice and queue != {"queue": "ywc_kor_procurement_notice_event", "kind": "notice", "mode": "exact", "value": 1034}:
                    raise ValueError("KOR procurement notice candidate has wrong queue shape")
                if nqg_aid_notice and queue != {"queue": "ywc_nqg_winter_aid_notice_event", "kind": "notice", "mode": "exact", "value": 1031}:
                    raise ValueError("NQG aid notice candidate has wrong queue shape")
                native_short = queue["queue"].split("_")[2] if is_nmg else None
                if is_mgl:
                    receipt_variable, receipt_value, receipt_match = None, None, True
                elif is_nmg:
                    receipt_variable, receipt_value = _nmg_native_receipt(event, native_short)
                    receipt_match = True
                else:
                    receipt_pattern = r"name\s*=\s*(ywc_v03_dmg_[a-z0-9_]*_last_event|ywc_nmg_[a-z0-9_]*_last_event)\s+value\s*=\s*([0-9]+)"
                    receipt_match = re.search(receipt_pattern, event["immediate"])
                if is_lan:
                    receipt_variable, receipt_value = None, None
                    nodes = parse_block(event["immediate"])
                    if len(nodes) != 1 or nodes[0].key != "ywc_v03_mark_major_delivered" or nodes[0].op != "=" or nodes[0].value != "yes":
                        raise ValueError(f"{event['id']}: unsupported LAN immediate body")
                elif is_shu:
                    receipt_variable, receipt_value = _shu_expected_receipt(event["id"])
                    native_receipt = re.search(rf"name\s*=\s*{re.escape(receipt_variable)}\s+value\s*=\s*([0-9]+)", event["immediate"])
                    if not native_receipt or int(native_receipt.group(1)) != receipt_value:
                        raise ValueError(f"{event['id']}: SHU immediate must write its exact native receipt")
                elif not (is_nmg or is_mgl):
                    receipt_variable = receipt_match.group(1) if receipt_match else None
                    receipt_value = int(receipt_match.group(2)) if receipt_match else None
                if is_mgl:
                    receipt_variable, receipt_value = None, None
                if not receipt_match and not (is_kor or is_nqg or is_shu or is_lan or is_nmg or is_mgl): raise ValueError(f"{event['id']}: source immediate lacks a last_event receipt")
                intent_variable = open_variable = None
                if is_nqg and queue["kind"] in {"notice12", "notice36"}:
                    suffix = "12" if queue["kind"] == "notice12" else "36"
                    stem = queue["queue"].removesuffix(f"notice{suffix}_pending")
                    intent_variable = stem + f"notice{suffix}_intent"
                    open_variable = stem + f"notice{suffix}_open"
                    receipt_variable = stem + f"blocked_{suffix}_delivered"
                native_return = None
                if is_nmg:
                    return_target = f"ywc_nmg_{native_short}_notice_return_event"
                    return_writes = []
                    for native_node in _walk(parse_block(event["immediate"])):
                        if native_node.key != "set_variable" or native_node.op != "=" or not isinstance(native_node.value, tuple):
                            continue
                        target_nodes = direct_values(children(native_node), "name")
                        if len(target_nodes) == 1 and target_nodes[0].op == "=" and target_nodes[0].value == return_target:
                            return_writes.append(native_node)
                    if return_writes:
                        if len(return_writes) != 1:
                            raise ValueError(f"{event['id']}: native notice return target must be written exactly once")
                        native_return = return_target
                native_context = f"ywc_nmg_{native_short}_notice_response_context" if native_return else None
                native_notice = bool(is_nmg and queue["queue"].endswith("_notice_pending"))
                native_threshold = {1006: 12, 1007: 36, 1014: 12, 1015: 36, 1028: 12, 1029: 36}.get(int(event["id"].rsplit(".", 1)[1])) if native_notice else None
                native_due = f"ywc_nmg_{native_short}_notice{native_threshold}_due" if native_threshold else None
                native_delivered = f"ywc_nmg_{native_short}_notice{native_threshold}_delivered" if native_threshold else None
                native_notice_marker = None
                native_notice_marker_value = None
                if is_mgl and queue["kind"] == "notice":
                    native_notice_marker = queue["queue"].split("_blocked_", 1)[0] + "_blocked_notice_last_delivered"
                    native_notice_marker_value = 1 if queue["queue"].endswith("_blocked_12_notice_event") else 2
                rank_map = ({"normal": 0, "notice": 1} if (is_kor or is_lan or is_nmg) else {"normal": 1, "notice": 0} if is_shu else {"normal": 0, "notice36": 1, "notice12": 2} if not is_nqg else {"normal_queued_event": 0, "notice36": 1, "notice12": 2, "remedy_final": 3, "notice": 4})
                if is_mgl:
                    rank_map = {"normal": 0, "notice": 1}
                candidates.append({"id": len(candidates) + 1, "key": f"c{len(candidates)+1}", "arc": arc, "journal": journal, "phase": phases[journal["id"]]["phase"], "branch": branch, "proof": proof, "queue": queue, "event": event, "receipt_variable": receipt_variable, "receipt_value": receipt_value, "intent_variable": intent_variable, "open_variable": open_variable, "native_return": native_return, "native_context": native_context, "native_notice": native_notice, "native_due": native_due, "native_delivered": native_delivered, "native_notice_marker": native_notice_marker, "native_notice_marker_value": native_notice_marker_value, "kor_instructor_notice": kor_instructor_notice, "kor_procurement_notice": kor_procurement_notice, "nqg_aid_notice": nqg_aid_notice, "rank": rank_map[queue["kind"]]})
    cid = lambda c: f"{prefix}_candidate_{c['id']}"
    turn = lambda c: f"{prefix}_turn_{c['id']}"
    dispatch = lambda c: f"{prefix}_dispatch_{c['id']}"
    roundv = f"{prefix}_round"
    reservation = f"{prefix}_reservation"
    epoch = f"{prefix}_reservation_epoch"
    timer = f"{prefix}_timer"
    served = {arc["slug"]: f"{prefix}_served_{arc_order[arc['slug']]+1}" for arc in arcs}
    triggers: list[str] = []
    effects: list[str] = []
    candidates_by_event: dict[str, list[dict[str, Any]]] = {}
    branches_by_journal: dict[str, dict[int, list[dict[str, Any]]]] = {}
    for c in candidates:
        branches_by_journal.setdefault(c["journal"]["id"], {}).setdefault(c["branch"]["branch_index"], []).append(c)
        candidates_by_event.setdefault(c["event"]["id"], []).append(c)
        source_inner = _mgl_inner_text if is_mgl else _inner_text
        lim = source_inner(c["branch"]["limit_source"][c["branch"]["limit_source"].find("{"):])
        event_guard = source_inner(c["event"]["trigger"])
        goal = source_inner(c["journal"]["goal"])
        fail = source_inner(c["journal"]["exit_conditions"])
        q = c["queue"]
        queue_gate = f"has_variable = {q['queue']}" if q["mode"] == "presence" else f"var:{q['queue']} = {q['value']}"
        source_class = "AND = { " + lim + " " + queue_gate + " }"
        parts = [f"has_journal_entry = {c['journal']['id']}", f"has_variable = {c['phase']['live_witness']}", source_class, event_guard]
        if is_mgl:
            parts.append(f"var:{c['phase']['live_witness']} = 1")
        if is_kor or is_nqg or is_shu or is_lan or is_mgl:
            for prior in c["proof"].get("chain_prior", []):
                parts.append("NOT = { " + _limit_inner_source(prior["limit_source"]) + " }")
        if is_nqg and c["event"]["id"] in {"ywc_nqg.1009", "ywc_nqg.1015", "ywc_nqg.1027"}:
            base = {"v03_nqg_winter_court": "winter", "v03_nqg_hunting_rights": "hunting", "v03_nqg_northern_port": "port"}[c["arc"]["slug"]]
            intent12 = f"ywc_nqg_{base}_notice12_intent"
            intent36 = f"ywc_nqg_{base}_notice36_intent"
            if c["queue"]["kind"] == "notice36":
                parts.append(f"NOT = {{ has_variable = {intent12} }}")
            elif c["queue"]["kind"] not in {"notice12"}:
                parts.extend((f"NOT = {{ has_variable = {intent12} }}", f"NOT = {{ has_variable = {intent36} }}"))
        if goal: parts.append(f"NOT = {{ {goal} }}")
        if fail: parts.append(f"NOT = {{ {fail} }}")
        triggers.append(f"{cid(c)} = {{ AND = {{ {' '.join(parts)} }} }}")
    # Per-candidate turn gate: dynamically compare only candidates that are live now.
    for c in candidates:
        slug = c["arc"]["slug"]; q = c["queue"]; blockers=[]
        # Rebuild all source-derived guards from this candidate. The earlier
        # candidate-predicate loop uses the same local names; relying on those
        # values here would leave every dispatch guard pinned to the final row.
        source_inner = _mgl_inner_text if is_mgl else _inner_text
        lim = source_inner(c["branch"]["limit_source"][c["branch"]["limit_source"].find("{"):])
        event_guard = source_inner(c["event"]["trigger"])
        goal = source_inner(c["journal"]["goal"])
        fail = source_inner(c["journal"]["exit_conditions"])
        queue_gate = f"has_variable = {q['queue']}" if q["mode"] == "presence" else f"var:{q['queue']} = {q['value']}"
        source_class = "AND = { " + lim + " " + queue_gate + " }"
        for other in candidates:
            if other["id"] == c["id"]: continue
            higher = other["rank"] > c["rank"]
            earlier_tie = other["rank"] == c["rank"] and (arc_order[other["arc"]["slug"]] < arc_order[slug] or (other["arc"]["slug"] == slug and other["id"] < c["id"]))
            if (higher or earlier_tie) and not (is_lan and other["arc"]["slug"] != slug) and not (is_nmg and other["arc"]["slug"] != slug) and not (is_mgl and other["arc"]["slug"] != slug):
                if other["arc"]["slug"] == slug:
                    blockers.append(f"{cid(other)} = yes")
                else:
                    blockers.append(f"AND = {{ {cid(other)} = yes NOT = {{ var:{served[other['arc']['slug']]} = var:{roundv} }} }}")
        eligibility_terms = [f"{cid(c)} = yes",f"NOT = {{ var:{served[slug]} = var:{roundv} }}"]
        if blockers: eligibility_terms.append("NOT = { OR = { "+" ".join(blockers)+" } }")
        terms=[*eligibility_terms,f"NOT = {{ has_variable = {reservation} }}",f"NOT = {{ has_variable = {timer} }}"]
        triggers.append(f"{turn(c)} = {{ AND = {{ {' '.join(terms)} }} }}")
        snapshot_present = _queue_snapshot_name(c["id"], q["queue"], "present", prefix)
        snapshot_value = _queue_snapshot_name(c["id"], q["queue"], "value", prefix)
        # Dispatch is revalidated at the native event trigger, before its immediate
        # can clear notice flags. This proves the same exact source queue and phase
        # still own the reservation; the ACK then uses the captured queue snapshot
        # because native DMG notice helpers intentionally clear both notice classes.
        dispatch_checks = [f"var:{reservation} = {c['id']}", f"has_variable = {timer}",
                           f"has_variable = {snapshot_present}", f"has_variable = {snapshot_value}",
                           f"has_variable = {q['queue']}", f"var:{q['queue']} = var:{snapshot_value}"]
        if is_nmg:
            # NMG queue snapshots record both presence and the exact selected
            # source event. Presence alone (or a present marker of 0/7) is not
            # sufficient authorization to enter the native event body.
            dispatch_checks += [f"var:{snapshot_present} = 1", f"var:{snapshot_value} = {q['value']}"]
        if is_mgl:
            dispatch_checks += [f"var:{snapshot_present} = 1", f"var:{snapshot_value} = {q['value']}"]
        if is_supported_inline_country and not is_shu:
            dispatch_checks += [f"has_variable = {epoch}", f"var:{epoch} > 0",
                                f"has_variable = {prefix}_candidate_epoch_{c['id']}",
                                f"var:{prefix}_candidate_epoch_{c['id']} > 0",
                                f"var:{prefix}_candidate_epoch_{c['id']} = var:{epoch}"]
        if is_lan:
            stem=q["queue"].split("_")[2]
            dispatch_checks += [f"has_journal_entry = {c['journal']['id']}", f"has_variable = {c['phase']['live_witness']}", source_class, event_guard]
            if goal: dispatch_checks.append(f"NOT = {{ {goal} }}")
            if fail: dispatch_checks.append(f"NOT = {{ {fail} }}")
            for prior in c["proof"].get("chain_prior", []):
                dispatch_checks.append("NOT = { " + _limit_inner_source(prior["limit_source"]) + " }")
            dispatch_checks.append(f"NOT = {{ var:{served[slug]} = var:{roundv} }}")
            dispatch_checks.extend(eligibility_terms[2:])
            tracked=[f"ywc_lan_{stem}_notice_current",f"ywc_lan_{stem}_notice12_sent",f"ywc_lan_{stem}_notice36_sent",f"ywc_lan_{stem}_pending_event",f"ywc_lan_{stem}_notice_event"]
            for name in dict.fromkeys(tracked):
                if q["kind"] == "notice" and name in {f"ywc_lan_{stem}_notice_current",f"ywc_lan_{stem}_notice{q['value']}_sent"}:
                    expected_post=str(q["value"]) if name.endswith("notice_current") else "1"
                    dispatch_checks += [f"has_variable = {name}",f"var:{name} = {expected_post}"]
                    continue
                pv=_queue_snapshot_name(c["id"],name,"present",prefix); vv=_queue_snapshot_name(c["id"],name,"value",prefix)
                dispatch_checks.append("OR = { "+f"AND = {{ has_variable = {pv} has_variable = {vv} var:{pv} = 1 has_variable = {name} var:{name} = var:{vv} }} "+f"AND = {{ has_variable = {pv} has_variable = {vv} var:{pv} = 0 var:{vv} = 0 NOT = {{ has_variable = {name} }} }} }}")
        elif is_nqg:
            dispatch_checks += [f"has_journal_entry = {c['journal']['id']}", f"has_variable = {c['phase']['live_witness']}", source_class, event_guard]
            if goal: dispatch_checks.append(f"NOT = {{ {goal} }}")
            if fail: dispatch_checks.append(f"NOT = {{ {fail} }}")
            for prior in c["proof"].get("chain_prior", []):
                dispatch_checks.append("NOT = { " + _limit_inner_source(prior["limit_source"]) + " }")
            dispatch_checks.append(f"NOT = {{ var:{served[slug]} = var:{roundv} }}")
            dispatch_checks.extend(eligibility_terms[2:])
        elif is_mgl:
            dispatch_checks += [f"has_journal_entry = {c['journal']['id']}",
                                f"has_variable = {c['phase']['live_witness']}", event_guard,
                                f"NOT = {{ var:{served[slug]} = var:{roundv} }}"]
            if goal: dispatch_checks.append(f"NOT = {{ {goal} }}")
            if fail: dispatch_checks.append(f"NOT = {{ {fail} }}")
            dispatch_checks.extend(_mgl_snapshot_checks(c, prefix))
        else:
            dispatch_checks += eligibility_terms
        # Preserve SHU's pre-existing term order byte-for-byte. Its original
        # four epoch checks were appended after eligibility terms; accepted4
        # epoch strengthening applies only to OIR/DMG/KOR/NQG.
        if is_shu:
            dispatch_checks += [f"has_variable = {epoch}", f"has_variable = {prefix}_candidate_epoch_{c['id']}",
                                f"var:{epoch} > 0", f"var:{prefix}_candidate_epoch_{c['id']} = var:{epoch}"]
        # Native DMG notice immediates can clear sibling notice queues and
        # their delivered markers. The event trigger (and the guarded
        # immediate preflight) must prove every captured sibling still has
        # the exact captured presence/value before those source helpers run.
        # This prevents an older reservation from restoring an absent queue,
        # a present-zero queue, or an older epoch over newer live state.
        notice_queues = sorted({
            candidate["queue"]["queue"]
            for candidate in candidates
            if candidate["arc"]["slug"] == c["arc"]["slug"]
            and candidate["queue"]["kind"].startswith("notice")
        }) if not (is_kor or is_lan or is_nmg or is_mgl) else []
        if not is_nqg:
            tracked = set()
            for notice in notice_queues:
                tracked.add(notice)
                if notice.endswith("_blocked_12_notice") or notice.endswith("_blocked_36_notice"):
                    tracked.add(notice.replace("_notice", "_delivered"))
            for name in sorted(tracked):
                present = _queue_snapshot_name(c["id"], name, "present", prefix)
                value = _queue_snapshot_name(c["id"], name, "value", prefix)
                dispatch_checks.append(
                    "OR = { "
                    f"AND = {{ has_variable = {present} has_variable = {value} "
                    f"has_variable = {name} var:{name} = var:{value} }} "
                    f"AND = {{ NOT = {{ has_variable = {present} }} "
                    f"NOT = {{ has_variable = {value} }} NOT = {{ has_variable = {name} }} }} "
                    "}"
                )
        if is_nqg:
            for name in _nqg_candidate_state(c, candidates):
                if name == c.get("intent_variable"):
                    dispatch_checks.append(f"has_variable = {name}")
                    dispatch_checks.append(f"var:{name} = 1")
                    continue
                present = _queue_snapshot_name(c["id"], name, "present", prefix)
                value = _queue_snapshot_name(c["id"], name, "value", prefix)
                dispatch_checks.append("OR = { "
                    f"AND = {{ has_variable = {present} has_variable = {value} has_variable = {name} var:{name} = var:{value} }} "
                    f"AND = {{ NOT = {{ has_variable = {present} }} NOT = {{ has_variable = {value} }} NOT = {{ has_variable = {name} }} }} }}")
        if q["mode"] == "exact":
            dispatch_checks.append(f"var:{snapshot_value} = {q['value']}")
        if c.get("kor_instructor_notice"):
            dispatch_checks.extend(_kor_instructor_checks(c["id"], delivered=True))
        if c.get("kor_procurement_notice"):
            dispatch_checks.extend(_kor_procurement_checks(c["id"], delivered=True))
        if c.get("nqg_aid_notice"):
            dispatch_checks.extend(_nqg_aid_checks(c["id"], delivered=True))
        triggers.append(f"{dispatch(c)} = {{ AND = {{ {' '.join(dispatch_checks)} }} }}")
    # Per-JE live witness and source lifecycle are handled by the journal renderer.
    any_candidates = " OR = { " + " ".join(f"{cid(c)} = yes" for c in candidates) + " }"
    reset_checks=[]
    for arc in arcs:
        slug=arc["slug"]; own=[c for c in candidates if c["arc"]["slug"]==slug]
        reset_checks.append("OR = { NOT = { OR = { "+" ".join(f"{cid(c)} = yes" for c in own)+" } } var:"+served[slug]+" = var:"+roundv+" }")
    kor_ephemeral: list[str] = []
    ephemeral_by_candidate: dict[int, list[str]] = {}
    if is_supported_inline_country:
        for c in candidates:
            ident=c["id"]; qvar=c["queue"]["queue"]
            names=[f"{prefix}_callback_{ident}", f"{prefix}_callback_candidate_{ident}",
                   f"{prefix}_callback_epoch_{ident}", f"{prefix}_callback_queue_{ident}",
                   f"{prefix}_candidate_epoch_{ident}", _queue_snapshot_name(ident,qvar,"present",prefix),
                   _queue_snapshot_name(ident,qvar,"value",prefix)]
            if is_lan:
                stem=qvar.split("_")[2]
                names += [f"{prefix}_rollback_armed_{ident}", f"{prefix}_body_completed_{ident}", f"{prefix}_body_completed_epoch_{ident}"]
                names += [f"{prefix}_snapshot_complete_{ident}"]
                tracked=[f"ywc_lan_{stem}_notice_current",f"ywc_lan_{stem}_notice12_sent",f"ywc_lan_{stem}_notice36_sent",f"ywc_lan_{stem}_pending_event",f"ywc_lan_{stem}_notice_event"]
                names += [_queue_snapshot_name(ident,state,suffix,prefix) for state in tracked for suffix in ("present","value")]
            if is_shu and ident == 2:
                names.extend([f"{prefix}_aux_waiting_present_2", f"{prefix}_aux_waiting_value_2"])
            if is_nqg:
                names.extend(_queue_snapshot_name(ident, state, suffix, prefix)
                             for state in _nqg_candidate_state(c, candidates) for suffix in ("present", "value"))
            if is_nmg and c.get("native_return"):
                names += [_queue_snapshot_name(ident, c["receipt_variable"], "native_present", prefix),
                          _queue_snapshot_name(ident, c["receipt_variable"], "native_value", prefix)]
            if is_nmg:
                names += [f"{prefix}_body_completed_{ident}", f"{prefix}_body_completed_epoch_{ident}"]
            if is_mgl:
                names += [f"{prefix}_body_completed_{ident}", f"{prefix}_body_completed_epoch_{ident}"]
                names += [_queue_snapshot_name(ident, state, suffix, prefix)
                          for state in _mgl_tracked_state(c) for suffix in ("present", "value")]
            if c.get("kor_instructor_notice"):
                names += list(_kor_instructor_fields(ident).values())
            if c.get("kor_procurement_notice"):
                names += list(_kor_procurement_fields(ident).values())
            if c.get("nqg_aid_notice"):
                names += list(_nqg_aid_fields(ident).values())
            ephemeral_by_candidate[ident] = names
            kor_ephemeral.extend(names)
    kor_cleanup = " ".join(f"remove_variable = {name}" for name in kor_ephemeral)
    shared_cleanup = f"{prefix}_clear_candidate_state"
    shared_cleanup_call = f"{shared_cleanup} = yes"
    if is_supported_inline_country and not is_shu:
        effects.append(f"{shared_cleanup} = {{ {kor_cleanup} }}")
    prep=[f"{prefix}_prepare = {{",f"    if = {{ limit = {{ NOT = {{ has_variable = {roundv} }} }} set_variable = {{ name = {roundv} value = 1 }} }}"]
    if is_lan:
        for c in candidates:
            ident=c["id"]; q=c["queue"]; stem=q["queue"].split("_")[2]
            armed=f"{prefix}_rollback_armed_{ident}"; completed=f"{prefix}_body_completed_{ident}"
            rollback=[]
            if q["kind"] == "notice":
                for name,post in ((f"ywc_lan_{stem}_notice_current",str(q["value"])),(f"ywc_lan_{stem}_notice{q['value']}_sent","1")):
                    pv=_queue_snapshot_name(ident,name,"present",prefix); vv=_queue_snapshot_name(ident,name,"value",prefix)
                    owned=f"has_variable = {pv} has_variable = {vv} OR = {{ AND = {{ var:{pv} = 1 has_variable = {name} var:{name} = {post} }} AND = {{ var:{pv} = 0 var:{vv} = 0 has_variable = {name} var:{name} = {post} }} }}"
                    restore=f"if = {{ limit = {{ var:{pv} = 1 }} set_variable = {{ name = {name} value = var:{vv} }} }} if = {{ limit = {{ var:{pv} = 0 var:{vv} = 0 }} remove_variable = {name} }}"
                    rollback.append(f"if = {{ limit = {{ has_variable = {prefix}_snapshot_complete_{ident} var:{prefix}_snapshot_complete_{ident} = 1 has_variable = {armed} var:{armed} = 1 NOT = {{ has_variable = {completed} }} {owned} }} {restore} }}")
            clear=" ".join(f"remove_variable = {x}" for x in ephemeral_by_candidate[ident]); base=f"var:{reservation} = {ident}"; roll=" ".join(rollback)
            prep.append(f"    if = {{ limit = {{ {base} NOT = {{ has_variable = {timer} }} }} {roll} remove_variable = {reservation} {clear} }}")
            prep.append(f"    if = {{ limit = {{ {base} has_variable = {timer} NOT = {{ {dispatch(c)} = yes }} }} {roll} remove_variable = {reservation} remove_variable = {timer} {clear} }}")
        known="OR = { "+" ".join(f"var:{reservation} = {c['id']}" for c in candidates)+" }"
        prep.append(f"    if = {{ limit = {{ has_variable = {reservation} NOT = {{ {known} }} }} remove_variable = {reservation} remove_variable = {timer} {shared_cleanup_call} }}")
    elif is_nqg:
        for c in candidates:
            ident=c["id"]; intent=c.get("intent_variable")
            baseguard=[f"var:{reservation} = {ident}"]
            rollback=""
            if intent:
                pvar=_queue_snapshot_name(ident,intent,"present",prefix)
                vvar=_queue_snapshot_name(ident,intent,"value",prefix)
                rollback=(f" if = {{ limit = {{ has_variable = {pvar} has_variable = {vvar} has_variable = {intent} var:{intent} = 1 }} set_variable = {{ name = {intent} value = var:{vvar} }} }}"
                          f" if = {{ limit = {{ NOT = {{ has_variable = {pvar} }} has_variable = {intent} var:{intent} = 1 }} remove_variable = {intent} }}")
            clear=shared_cleanup_call
            stale_cond=f"AND = {{ {' '.join(baseguard)} {cid(c)} = no }}"
            prep.append(f"    if = {{ limit = {{ {stale_cond} }}{rollback} remove_variable = {reservation} remove_variable = {timer} {clear} }}")
            expired_cond=f"AND = {{ {' '.join(baseguard)} NOT = {{ has_variable = {timer} }} }}"
            prep.append(f"    if = {{ limit = {{ {expired_cond} }}{rollback} remove_variable = {reservation} {clear} }}")
        known_ids = "OR = { " + " ".join(f"var:{reservation} = {c['id']}" for c in candidates) + " }"
        unknown_clear=shared_cleanup_call
        prep.append(f"    if = {{ limit = {{ has_variable = {reservation} NOT = {{ {known_ids} }} }} remove_variable = {reservation} remove_variable = {timer} {unknown_clear} }}")
    elif is_shu:
        for c in candidates:
            ident=c["id"]
            clear=" ".join(f"remove_variable = {name}" for name in ephemeral_by_candidate[ident])
            rollback=""
            if ident == 2:
                ap=f"{prefix}_aux_waiting_present_2"; av=f"{prefix}_aux_waiting_value_2"; aux="ywc_shu_waiting_for_capacity"
                rollback=f" if = {{ limit = {{ has_variable = {ap} has_variable = {av} NOT = {{ has_variable = {aux} }} }} set_variable = {{ name = {aux} value = var:{av} }} }}"
            # Cleanup follows the recorded reservation ID, not its epoch
            # proof: stale or missing proof must not strand an expired slot.
            # Restore candidate 2's aux only from its complete owned snapshot.
            base=f"var:{reservation} = {ident}"
            prep.append(f"    if = {{ limit = {{ {base} NOT = {{ has_variable = {timer} }} }}{rollback} remove_variable = {reservation} {clear} }}")
            prep.append(f"    if = {{ limit = {{ has_variable = {timer} {base} {cid(c)} = no }}{rollback} remove_variable = {reservation} remove_variable = {timer} {clear} }}")
        known_ids = "OR = { " + " ".join(f"var:{reservation} = {c['id']}" for c in candidates) + " }"
        unknown_clear=" ".join(f"remove_variable = {name}" for name in kor_ephemeral)
        prep.append(f"    if = {{ limit = {{ has_variable = {reservation} NOT = {{ {known_ids} }} NOT = {{ has_variable = {timer} }} }} remove_variable = {reservation} {unknown_clear} }}")
        prep.append(f"    if = {{ limit = {{ has_variable = {reservation} NOT = {{ {known_ids} }} has_variable = {timer} }} remove_variable = {reservation} remove_variable = {timer} {unknown_clear} }}")
    elif is_nmg:
        # An identified NMG reservation is private protocol state. While its
        # timer is live, retain it only when the full native dispatch predicate
        # still holds; otherwise release its private slot and proof material.
        # No native queue, last_event, notice, or cooldown state is restored or
        # rewritten here because the native event body may already have run.
        known_ids = "OR = { " + " ".join(f"var:{reservation} = {c['id']}" for c in candidates) + " }"
        for c in candidates:
            ident = c["id"]
            base = f"var:{reservation} = {ident}"
            clear = " ".join(f"remove_variable = {name}" for name in ephemeral_by_candidate[ident])
            prep.append(f"    if = {{ limit = {{ {base} NOT = {{ has_variable = {timer} }} }} remove_variable = {reservation} {clear} }}")
            prep.append(f"    if = {{ limit = {{ has_variable = {timer} {base} NOT = {{ {dispatch(c)} = yes }} }} remove_variable = {reservation} remove_variable = {timer} {clear} }}")
        unknown_clear = " ".join(f"remove_variable = {name}" for name in kor_ephemeral)
        prep.append(f"    if = {{ limit = {{ has_variable = {reservation} NOT = {{ {known_ids} }} }} remove_variable = {reservation} remove_variable = {timer} {unknown_clear} }}")
    elif is_mgl:
        # MGL reservations are valid only while the exact source candidate,
        # positive epoch, live timer and phase witness still authorize dispatch.
        # Invalid or expired reservations release adapter-private fields only;
        # native queues and notice markers may already reflect a completed body.
        known_ids = "OR = { " + " ".join(f"var:{reservation} = {c['id']}" for c in candidates) + " }"
        for c in candidates:
            ident = c["id"]
            base = f"var:{reservation} = {ident}"
            clear = " ".join(f"remove_variable = {name}" for name in ephemeral_by_candidate[ident])
            prep.append(f"    if = {{ limit = {{ {base} NOT = {{ has_variable = {timer} }} }} remove_variable = {reservation} {clear} }}")
            prep.append(f"    if = {{ limit = {{ has_variable = {timer} {base} NOT = {{ {dispatch(c)} = yes }} }} remove_variable = {reservation} remove_variable = {timer} {clear} }}")
        prep.append(f"    if = {{ limit = {{ has_variable = {reservation} NOT = {{ {known_ids} }} }} remove_variable = {reservation} remove_variable = {timer} {shared_cleanup_call} }}")
    else:
        prep.append(f"    if = {{ limit = {{ has_variable = {reservation} NOT = {{ has_variable = {timer} }} }} remove_variable = {reservation} {shared_cleanup_call} }}")
        known_ids = "OR = { " + " ".join(f"var:{reservation} = {c['id']}" for c in candidates) + " }"
        prep.append(f"    if = {{ limit = {{ has_variable = {reservation} NOT = {{ {known_ids} }} }} remove_variable = {reservation} remove_variable = {timer} {shared_cleanup_call} }}")
    stale=" OR = { "+" ".join(f"AND = {{ var:{reservation} = {c['id']} NOT = {{ {cid(c)} = yes }} }}" for c in candidates)+" }"
    if not is_nqg:
        stale_cleanup=kor_cleanup if is_shu else shared_cleanup_call
        prep.append(f"    if = {{ limit = {{ has_variable = {timer} {stale} }} remove_variable = {reservation} remove_variable = {timer}{(' ' + stale_cleanup) if stale_cleanup else ''} }}")
    prep.append(f"    if = {{ limit = {{ {any_candidates} AND = {{ {' '.join(reset_checks)} }} }} change_variable = {{ name = {roundv} add = 1 }} }}")
    prep.append("}"); effects.extend(prep)
    # Reservation captures exact source values before any native pre-trigger removal/helper.
    for c in candidates:
        q=c["queue"]; qvar=q["queue"]; ident=c["id"]
        snap_present=_queue_snapshot_name(ident,qvar,"present",prefix); snap_value=_queue_snapshot_name(ident,qvar,"value",prefix)
        callback_proof = f"{prefix}_callback_{ident}"
        callback_id = f"{prefix}_callback_candidate_{ident}"
        callback_epoch = f"{prefix}_callback_epoch_{ident}"
        callback_queue = f"{prefix}_callback_queue_{ident}"
        notice_queues=sorted({x["queue"]["queue"] for x in candidates if x["arc"]["slug"]==c["arc"]["slug"] and x["queue"]["kind"].startswith("notice")}) if not (is_lan or is_nmg or is_mgl) else []
        capture=[f"if = {{ limit = {{ {turn(c)} = yes {cid(c)} = yes NOT = {{ has_variable = {reservation} }} }}"]
        if is_supported_inline_country and not is_shu:
            capture += [f"    {shared_cleanup_call}"]
            capture += [f"    if = {{ limit = {{ has_variable = {epoch} }} if = {{ limit = {{ var:{epoch} > 0 }} change_variable = {{ name = {epoch} add = 1 }} }} if = {{ limit = {{ NOT = {{ var:{epoch} > 0 }} }} set_variable = {{ name = {epoch} value = 1 }} }} }} if = {{ limit = {{ NOT = {{ has_variable = {epoch} }} }} set_variable = {{ name = {epoch} value = 1 }} }}"]
            capture += [f"    set_variable = {{ name = {prefix}_candidate_epoch_{ident} value = var:{epoch} }}"]
        elif is_supported_inline_country:
            capture += [f"    if = {{ limit = {{ has_variable = {epoch} }} change_variable = {{ name = {epoch} add = 1 }} }}", f"    if = {{ limit = {{ NOT = {{ has_variable = {epoch} }} }} set_variable = {{ name = {epoch} value = 1 }} }}"]
            capture += [f"    remove_variable = {name}" for name in (ephemeral_by_candidate[ident] if is_nqg else kor_ephemeral)]
            capture += [f"    set_variable = {{ name = {prefix}_candidate_epoch_{ident} value = var:{epoch} }}"]
        capture += [f"    set_variable = {{ name = {reservation} value = {ident} }}",f"    set_variable = {{ name = {snap_present} value = 1 }}",f"    set_variable = {{ name = {snap_value} value = var:{qvar} }}",f"    set_variable = {{ name = {timer} value = 1 days = 1 }}"]
        if c.get("kor_instructor_notice"):
            f = _kor_instructor_fields(ident)
            capture += [f"    set_variable = {{ name = {f[suffix]} value = var:ywc_kor_instructor_notice_{suffix} }}"
                        for suffix in ("serial", "generation", "request_state", "reason")]
            capture += [f"    remove_variable = {f['partner']}",
                        f"    set_variable = {{ name = {f['partner_available']} value = 0 }}",
                        f"    if = {{ limit = {{ exists = var:ywc_kor_instructor_notice_partner "
                        f"var:ywc_kor_instructor_notice_partner = {{ is_country_alive = yes }} }} "
                        f"set_variable = {{ name = {f['partner']} value = var:ywc_kor_instructor_notice_partner }} "
                        f"set_variable = {{ name = {f['partner_available']} value = 1 }} }}"]
        if c.get("kor_procurement_notice"):
            f = _kor_procurement_fields(ident)
            capture += [f"    set_variable = {{ name = {f[suffix]} value = var:ywc_kor_procurement_notice_{suffix} }}"
                        for suffix in ("serial", "generation", "request_state", "reason")]
            capture += [f"    remove_variable = {f['partner']}",
                        f"    set_variable = {{ name = {f['partner_available']} value = 0 }}",
                        f"    if = {{ limit = {{ exists = var:ywc_kor_procurement_notice_partner "
                        f"var:ywc_kor_procurement_notice_partner = {{ is_country_alive = yes }} }} "
                        f"set_variable = {{ name = {f['partner']} value = var:ywc_kor_procurement_notice_partner }} "
                        f"set_variable = {{ name = {f['partner_available']} value = 1 }} }}"]
        if c.get("nqg_aid_notice"):
            f = _nqg_aid_fields(ident)
            capture += [f"    set_variable = {{ name = {f[suffix]} value = var:ywc_nqg_winter_aid_notice_{suffix} }}"
                        for suffix in ("serial", "generation", "request_state", "reason")]
            capture += [f"    remove_variable = {f['partner']}",
                        f"    set_variable = {{ name = {f['partner_available']} value = 0 }}",
                        f"    if = {{ limit = {{ exists = var:ywc_nqg_winter_aid_notice_partner "
                        f"var:ywc_nqg_winter_aid_notice_partner = {{ is_country_alive = yes }} }} "
                        f"set_variable = {{ name = {f['partner']} value = var:ywc_nqg_winter_aid_notice_partner }} "
                        f"set_variable = {{ name = {f['partner_available']} value = 1 }} }}"]
        if is_lan:
            stem=qvar.split("_")[2]
            tracked=[f"ywc_lan_{stem}_notice_current",f"ywc_lan_{stem}_notice12_sent",f"ywc_lan_{stem}_notice36_sent",f"ywc_lan_{stem}_pending_event",f"ywc_lan_{stem}_notice_event"]
            for name in dict.fromkeys(tracked):
                pv=_queue_snapshot_name(ident,name,"present",prefix); vv=_queue_snapshot_name(ident,name,"value",prefix)
                capture += [f"    set_variable = {{ name = {pv} value = 0 }}",f"    set_variable = {{ name = {vv} value = 0 }}",f"    if = {{ limit = {{ has_variable = {name} }} set_variable = {{ name = {pv} value = 1 }} set_variable = {{ name = {vv} value = var:{name} }} }}"]
            if q["kind"] == "notice": capture += [f"    set_variable = {{ name = {prefix}_rollback_armed_{ident} value = 1 }}"]
            capture += [f"    set_variable = {{ name = {prefix}_snapshot_complete_{ident} value = 1 }}"]
            capture += [f"    remove_variable = {prefix}_body_completed_{ident}",f"    remove_variable = {prefix}_body_completed_epoch_{ident}"]
        elif is_nqg:
            for name in _nqg_candidate_state(c, candidates):
                pvar=_queue_snapshot_name(ident,name,"present",prefix); vvar=_queue_snapshot_name(ident,name,"value",prefix)
                capture += [f"    remove_variable = {pvar}", f"    remove_variable = {vvar}", f"    if = {{ limit = {{ has_variable = {name} }} set_variable = {{ name = {pvar} value = 1 }} set_variable = {{ name = {vvar} value = var:{name} }} }}"]
        elif is_mgl:
            for name in _mgl_tracked_state(c):
                pvar = _queue_snapshot_name(ident, name, "present", prefix)
                vvar = _queue_snapshot_name(ident, name, "value", prefix)
                capture += [f"    remove_variable = {pvar}", f"    remove_variable = {vvar}",
                            f"    set_variable = {{ name = {pvar} value = 0 }}", f"    set_variable = {{ name = {vvar} value = 0 }}",
                            f"    if = {{ limit = {{ has_variable = {name} }} set_variable = {{ name = {pvar} value = 1 }} set_variable = {{ name = {vvar} value = var:{name} }} }}"]
            capture += [f"    remove_variable = {prefix}_body_completed_{ident}",
                        f"    remove_variable = {prefix}_body_completed_epoch_{ident}"]
        else:
            if is_shu and ident == 2:
                ap=f"{prefix}_aux_waiting_present_2"; av=f"{prefix}_aux_waiting_value_2"; aux="ywc_shu_waiting_for_capacity"
                capture += [f"    remove_variable = {ap}", f"    remove_variable = {av}", f"    if = {{ limit = {{ has_variable = {aux} }} set_variable = {{ name = {ap} value = 1 }} set_variable = {{ name = {av} value = var:{aux} }} }}"]
            for notice in notice_queues:
                for name in (notice, notice.replace("_notice", "_delivered")):
                    if name==qvar and name.endswith("_notice"): continue
                    pvar=_queue_snapshot_name(ident,name,"present",prefix); vvar=_queue_snapshot_name(ident,name,"value",prefix)
                    capture += [f"    remove_variable = {pvar}", f"    remove_variable = {vvar}", f"    if = {{ limit = {{ has_variable = {name} }} set_variable = {{ name = {pvar} value = 1 }} set_variable = {{ name = {vvar} value = var:{name} }} }}"]
        if is_nmg and c.get("native_return"):
            pvar = _queue_snapshot_name(ident, c["receipt_variable"], "native_present", prefix)
            vvar = _queue_snapshot_name(ident, c["receipt_variable"], "native_value", prefix)
            capture += [f"    set_variable = {{ name = {pvar} value = 0 }}", f"    set_variable = {{ name = {vvar} value = 0 }}",
                        f"    if = {{ limit = {{ has_variable = {c['receipt_variable']} }} set_variable = {{ name = {pvar} value = 1 }} set_variable = {{ name = {vvar} value = var:{c['receipt_variable']} }} }}"]
        capture.append("}")
        effects.append(f"{prefix}_reserve_{ident} = {{ {' '.join(capture)} }}")
        # ACK is callable only from this event's actual immediate hook and must match receipt + reservation.
        ack=f"{prefix}_ack_{ident}"
        if is_supported_inline_country:
            checks=[f"var:{reservation} = {ident}",f"has_variable = {timer}",f"has_variable = {snap_present}",f"has_variable = {snap_value}",f"has_journal_entry = {c['journal']['id']}",f"has_variable = {c['phase']['live_witness']}"]
            checks += [f"has_variable = {callback_proof}", f"var:{callback_id} = {ident}", f"var:{callback_epoch} = var:{epoch}", f"var:{prefix}_candidate_epoch_{ident} = var:{epoch}", f"var:{callback_queue} = var:{snap_value}"]
            if is_shu:
                checks += [f"has_variable = {q['queue']}", f"var:{q['queue']} = var:{snap_value}", f"NOT = {{ var:{served[c['arc']['slug']]} = var:{roundv} }}"]
            else:
                checks.append(f"NOT = {{ var:{served[c['arc']['slug']]} = var:{roundv} }}")
                consumed = _dmg_native_notice_consumption(c) if is_dmg else None
                if consumed:
                    checks.append("OR = { AND = { has_variable = " + q["queue"] + f" var:{q['queue']} = var:{snap_value} }} {consumed} }}")
                else:
                    checks += [f"has_variable = {q['queue']}", f"var:{q['queue']} = var:{snap_value}"]
            if not is_shu:
                checks += [f"var:{callback_proof} = 1",f"has_variable = {callback_id}",f"has_variable = {callback_epoch}",f"has_variable = {epoch}",f"var:{epoch} > 0",f"has_variable = {callback_queue}"]
            if (is_dmg or is_nmg) and c.get("receipt_variable") and type(c.get("receipt_value")) is int:
                checks += [f"has_variable = {c['receipt_variable']}",f"var:{c['receipt_variable']} = {c['receipt_value']}"]
            checks += _nmg_native_postchecks(c, prefix) if is_nmg else []
            if is_nmg:
                checks += [f"has_variable = {prefix}_body_completed_{ident}", f"var:{prefix}_body_completed_{ident} = 1",
                           f"has_variable = {prefix}_body_completed_epoch_{ident}", f"var:{prefix}_body_completed_epoch_{ident} = var:{epoch}"]
            if is_mgl:
                checks += [f"has_variable = {prefix}_body_completed_{ident}", f"var:{prefix}_body_completed_{ident} = 1",
                           f"has_variable = {prefix}_body_completed_epoch_{ident}", f"var:{prefix}_body_completed_epoch_{ident} = var:{epoch}"]
                checks += _mgl_snapshot_checks(c, prefix)
            if is_shu:
                checks += [f"has_variable = {epoch}", f"has_variable = {prefix}_candidate_epoch_{ident}",
                           f"var:{epoch} > 0",
                           f"var:{callback_proof} = 1", f"has_variable = {callback_id}",
                           f"has_variable = {callback_epoch}", f"has_variable = {callback_queue}"]
        else:
            checks=[f"var:{reservation} = {ident}",f"has_variable = {timer}",f"has_variable = {snap_present}",f"has_variable = {snap_value}",f"has_journal_entry = {c['journal']['id']}",f"has_variable = {c['phase']['live_witness']}",f"has_variable = {callback_proof}",f"var:{callback_proof} = 1",f"has_variable = {callback_id}",f"var:{callback_id} = {ident}",f"has_variable = {callback_epoch}",f"has_variable = {epoch}",f"var:{callback_epoch} = var:{epoch}",f"has_variable = {prefix}_candidate_epoch_{ident}",f"var:{prefix}_candidate_epoch_{ident} = var:{epoch}",f"has_variable = {callback_queue}",f"var:{callback_queue} = var:{snap_value}",f"NOT = {{ var:{served[c['arc']['slug']]} = var:{roundv} }}"]
            consumed = _dmg_native_notice_consumption(c) if is_dmg else None
            if consumed:
                checks.append("OR = { AND = { has_variable = " + q["queue"] + f" var:{q['queue']} = var:{snap_value} }} {consumed} }}")
            else:
                checks += [f"has_variable = {q['queue']}",f"var:{q['queue']} = var:{snap_value}"]
        source_inner = _mgl_inner_text if is_mgl else _inner_text
        goal=source_inner(c["journal"]["goal"]); fail=source_inner(c["journal"]["exit_conditions"])
        if goal and not (is_shu or is_lan): checks.append(f"NOT = {{ {goal} }}")
        if fail and not (is_shu or is_lan): checks.append(f"NOT = {{ {fail} }}")
        if is_lan:
            checks += [f"has_variable = {prefix}_body_completed_{ident}",f"var:{prefix}_body_completed_{ident} = 1",f"has_variable = {prefix}_body_completed_epoch_{ident}",f"var:{prefix}_body_completed_epoch_{ident} = var:{epoch}",f"has_variable = {epoch}",f"var:{epoch} > 0"]
            stem=qvar.split("_")[2]
            expected_aux=((f"ywc_lan_{stem}_notice_current",str(q["value"])),(f"ywc_lan_{stem}_notice{q['value']}_sent","1")) if q["kind"] == "notice" else ()
            for name,value in expected_aux: checks += [f"has_variable = {name}",f"var:{name} = {value}"]
        if q["mode"]=="exact": checks.append(f"var:{snap_value} = {q['value']}")
        if c.get("kor_instructor_notice"):
            f = _kor_instructor_fields(ident)
            checks.extend(_kor_instructor_checks(ident, delivered=True))
            checks += [f"has_variable = {f['body_completed']}", f"var:{f['body_completed']} = 1",
                       f"has_variable = {f['body_completed_epoch']}",
                       f"var:{f['body_completed_epoch']} = var:{epoch}",
                       f"has_variable = {f['body_completed_serial']}",
                       f"var:{f['body_completed_serial']} = scope:ywc_kor_notice_serial",
                       "has_variable = ywc_kor_instructor_notice_open_serial",
                       "var:ywc_kor_instructor_notice_open_serial = scope:ywc_kor_notice_serial"]
        if c.get("kor_procurement_notice"):
            f = _kor_procurement_fields(ident)
            checks.extend(_kor_procurement_checks(ident, delivered=True))
            checks += [f"has_variable = {f['body_completed']}", f"var:{f['body_completed']} = 1",
                       f"has_variable = {f['body_completed_epoch']}",
                       f"var:{f['body_completed_epoch']} = var:{epoch}",
                       f"has_variable = {f['body_completed_serial']}",
                       f"var:{f['body_completed_serial']} = scope:ywc_kor_procurement_notice_serial",
                       "has_variable = ywc_kor_procurement_notice_open_serial",
                       "var:ywc_kor_procurement_notice_open_serial = scope:ywc_kor_procurement_notice_serial"]
        if c.get("nqg_aid_notice"):
            f = _nqg_aid_fields(ident)
            checks.extend(_nqg_aid_checks(ident, delivered=True))
            checks += [f"has_variable = {f['body_completed']}", f"var:{f['body_completed']} = 1",
                       f"has_variable = {f['body_completed_epoch']}",
                       f"var:{f['body_completed_epoch']} = var:{epoch}",
                       f"has_variable = {f['body_completed_serial']}",
                       f"var:{f['body_completed_serial']} = scope:ywc_nqg_winter_aid_notice_serial",
                       "has_variable = ywc_nqg_winter_aid_notice_open_serial",
                       "var:ywc_nqg_winter_aid_notice_open_serial = scope:ywc_nqg_winter_aid_notice_serial"]
        if is_lan:
            stem=qvar.split("_")[2]
            tracked=[f"ywc_lan_{stem}_notice_current",f"ywc_lan_{stem}_notice12_sent",f"ywc_lan_{stem}_notice36_sent",f"ywc_lan_{stem}_pending_event",f"ywc_lan_{stem}_notice_event"]
            for name in dict.fromkeys(tracked):
                if q["kind"] == "notice" and name in {f"ywc_lan_{stem}_notice_current",f"ywc_lan_{stem}_notice{q['value']}_sent"}:
                    post=str(q["value"]) if name.endswith("notice_current") else "1"
                    checks += [f"has_variable = {name}",f"var:{name} = {post}"]
                    continue
                pv=_queue_snapshot_name(ident,name,"present",prefix); vv=_queue_snapshot_name(ident,name,"value",prefix)
                checks.append("OR = { "+f"AND = {{ has_variable = {pv} has_variable = {vv} var:{pv} = 1 has_variable = {name} var:{name} = var:{vv} }} "+f"AND = {{ has_variable = {pv} has_variable = {vv} var:{pv} = 0 var:{vv} = 0 NOT = {{ has_variable = {name} }} }} }}")
        restore=[]
        for notice in notice_queues:
            if notice==qvar: continue
            pvar=_queue_snapshot_name(ident,notice,"present",prefix); vvar=_queue_snapshot_name(ident,notice,"value",prefix)
            restore += [f"remove_variable = {notice}",f"if = {{ limit = {{ has_variable = {pvar} }} set_variable = {{ name = {notice} value = var:{vvar} }} }}"]
            marker=notice.replace("_notice","_delivered")
            if notice.endswith("_blocked_12_notice") or notice.endswith("_blocked_36_notice"):
                mp=_queue_snapshot_name(ident,marker,"present",prefix); mv=_queue_snapshot_name(ident,marker,"value",prefix)
                restore += [f"remove_variable = {marker}",f"if = {{ limit = {{ has_variable = {mp} }} set_variable = {{ name = {marker} value = var:{mv} }} }}"]
        body_parts=[f"remove_variable = {qvar}",*restore,f"set_variable = {{ name = {served[c['arc']['slug']]} value = var:{roundv} }}",f"remove_variable = {reservation}",f"remove_variable = {timer}"]
        body_parts += [f"remove_variable = {callback_proof}",f"remove_variable = {callback_id}",f"remove_variable = {callback_epoch}",f"remove_variable = {callback_queue}",f"remove_variable = {prefix}_candidate_epoch_{ident}"]
        if not is_shu:
            body_parts += [shared_cleanup_call]
        elif is_nqg:
            body_parts += [f"remove_variable = {name}" for name in ephemeral_by_candidate[ident]]
        body=" ".join(body_parts)
        effects.append(f"{prefix}_ack_{ident} = {{ if = {{ limit = {{ {' '.join(checks)} }} {body} }} }}")
        if is_supported_inline_country:
            callback_guard = [f"var:{reservation} = {ident}", f"has_variable = {timer}", f"has_variable = {snap_present}", f"has_variable = {snap_value}", f"has_variable = {qvar}", f"var:{qvar} = var:{snap_value}", f"has_journal_entry = {c['journal']['id']}", f"has_variable = {c['phase']['live_witness']}"]
            if q["mode"] == "exact": callback_guard.append(f"var:{snap_value} = {q['value']}")
            if c.get("kor_instructor_notice"):
                f = _kor_instructor_fields(ident)
                callback_guard.extend(_kor_instructor_checks(ident, delivered=True))
                callback_guard += [f"has_variable = {f['body_completed']}",
                                   f"var:{f['body_completed']} = 1",
                                   f"var:{f['body_completed_epoch']} = var:{epoch}",
                                   f"var:{f['body_completed_serial']} = scope:ywc_kor_notice_serial",
                                   "var:ywc_kor_instructor_notice_open_serial = scope:ywc_kor_notice_serial"]
            if c.get("kor_procurement_notice"):
                f = _kor_procurement_fields(ident)
                callback_guard.extend(_kor_procurement_checks(ident, delivered=True))
                callback_guard += [f"has_variable = {f['body_completed']}",
                                   f"var:{f['body_completed']} = 1",
                                   f"var:{f['body_completed_epoch']} = var:{epoch}",
                                   f"var:{f['body_completed_serial']} = scope:ywc_kor_procurement_notice_serial",
                                   "var:ywc_kor_procurement_notice_open_serial = scope:ywc_kor_procurement_notice_serial"]
            if c.get("nqg_aid_notice"):
                f = _nqg_aid_fields(ident)
                callback_guard.extend(_nqg_aid_checks(ident, delivered=True))
                callback_guard += [f"has_variable = {f['body_completed']}",
                                   f"var:{f['body_completed']} = 1",
                                   f"var:{f['body_completed_epoch']} = var:{epoch}",
                                   f"var:{f['body_completed_serial']} = scope:ywc_nqg_winter_aid_notice_serial",
                                   "var:ywc_nqg_winter_aid_notice_open_serial = scope:ywc_nqg_winter_aid_notice_serial"]
            if goal and not (is_shu or is_lan): callback_guard.append(f"NOT = {{ {goal} }}")
            if fail and not (is_shu or is_lan): callback_guard.append(f"NOT = {{ {fail} }}")
            callback_guard.append(f"NOT = {{ var:{served[c['arc']['slug']]} = var:{roundv} }}")
            callback_guard += [f"has_variable = {epoch}",
                               f"has_variable = {prefix}_candidate_epoch_{ident}",
                               f"var:{epoch} > 0",
                               f"var:{prefix}_candidate_epoch_{ident} = var:{epoch}"]
            if is_lan:
                callback_guard += [f"has_variable = {prefix}_body_completed_{ident}",f"var:{prefix}_body_completed_{ident} = 1",f"has_variable = {prefix}_body_completed_epoch_{ident}",f"var:{prefix}_body_completed_epoch_{ident} = var:{epoch}"]
                stem=qvar.split("_")[2]
                tracked=[f"ywc_lan_{stem}_notice_current",f"ywc_lan_{stem}_notice12_sent",f"ywc_lan_{stem}_notice36_sent",f"ywc_lan_{stem}_pending_event",f"ywc_lan_{stem}_notice_event"]
                for name in dict.fromkeys(tracked):
                    if q["kind"] == "notice" and name in {f"ywc_lan_{stem}_notice_current",f"ywc_lan_{stem}_notice{q['value']}_sent"}:
                        post=str(q["value"]) if name.endswith("notice_current") else "1"
                        callback_guard += [f"has_variable = {name}",f"var:{name} = {post}"]
                        continue
                    pv=_queue_snapshot_name(ident,name,"present",prefix); vv=_queue_snapshot_name(ident,name,"value",prefix)
                    callback_guard.append("OR = { "+f"AND = {{ has_variable = {pv} has_variable = {vv} var:{pv} = 1 has_variable = {name} var:{name} = var:{vv} }} "+f"AND = {{ has_variable = {pv} has_variable = {vv} var:{pv} = 0 var:{vv} = 0 NOT = {{ has_variable = {name} }} }} }}")
            if is_mgl:
                callback_guard += [f"has_variable = {prefix}_body_completed_{ident}",
                                   f"var:{prefix}_body_completed_{ident} = 1",
                                   f"has_variable = {prefix}_body_completed_epoch_{ident}",
                                   f"var:{prefix}_body_completed_epoch_{ident} = var:{epoch}"]
                callback_guard.extend(_mgl_snapshot_checks(c, prefix))
            if is_nqg:
                callback_guard.append(f"var:{prefix}_candidate_epoch_{ident} = var:{epoch}")
                calls_notice_helper = _nqg_event_calls_notice_helper(c["event"], c["arc"]["slug"])
                if c["queue"]["kind"] in {"notice12", "notice36"}:
                    if not calls_notice_helper:
                        raise ValueError(f"{c['event']['id']}: notice candidate has no native notice delivery helper")
                    callback_guard.extend([f"NOT = {{ has_variable = {c['intent_variable']} }}", f"has_variable = {c['receipt_variable']}", f"var:{c['receipt_variable']} = 1", f"has_variable = {c['open_variable']}", f"var:{c['open_variable']} = 1"])
                elif calls_notice_helper:
                    base = {"v03_nqg_winter_court": "winter", "v03_nqg_hunting_rights": "hunting", "v03_nqg_northern_port": "port"}[c["arc"]["slug"]]
                    callback_guard.extend([f"NOT = {{ has_variable = ywc_nqg_{base}_notice12_intent }}", f"NOT = {{ has_variable = ywc_nqg_{base}_notice36_intent }}"])
                for name in _nqg_candidate_state(c, candidates):
                    if name in {c.get("intent_variable"), c.get("receipt_variable"), c.get("open_variable")}:
                        continue
                    pvar = _queue_snapshot_name(ident, name, "present", prefix); vvar = _queue_snapshot_name(ident, name, "value", prefix)
                    callback_guard.append("OR = { "
                        f"AND = {{ has_variable = {pvar} has_variable = {vvar} has_variable = {name} var:{name} = var:{vvar} }} "
                        f"AND = {{ NOT = {{ has_variable = {pvar} }} NOT = {{ has_variable = {vvar} }} NOT = {{ has_variable = {name} }} }} }}")
            if is_shu:
                callback_guard.extend([f"has_variable = {callback_proof}", f"var:{callback_proof} = 1",
                                       f"has_variable = {callback_id}", f"var:{callback_id} = {ident}",
                                       f"has_variable = {callback_epoch}", f"var:{callback_epoch} = var:{epoch}",
                                       f"has_variable = {callback_queue}", f"var:{callback_queue} = var:{snap_value}",
                                       f"var:{prefix}_candidate_epoch_{ident} = var:{epoch}",
                                       f"has_variable = {c['receipt_variable']}", f"var:{c['receipt_variable']} = {c['receipt_value']}"])
                effects.append(f"{prefix}_callback_{ident} = {{ if = {{ limit = {{ {' '.join(callback_guard)} }} {prefix}_ack_{ident} = yes }} }}")
            else:
                effects.append(f"{prefix}_callback_{ident} = {{ if = {{ limit = {{ {' '.join(callback_guard)} has_variable = {callback_proof} var:{callback_proof} = 1 has_variable = {callback_id} var:{callback_id} = {ident} has_variable = {callback_epoch} var:{callback_epoch} = var:{epoch} has_variable = {callback_queue} var:{callback_queue} = var:{snap_value} }} {prefix}_ack_{ident} = yes }} }}")
    journal_scripts={}
    # Splice only proven sender limits and insert candidate-owned reservations before native source ops.
    for journal_id, journal_info in phases.items():
        journal=journal_info["journal"]; script=journal["script"]; binding=_mgl_source_binding(journal_id,script) if is_mgl else _nmg_source_binding(journal_id,script) if is_nmg else _lan_source_binding(journal_id,script) if is_lan else _kor_source_binding(journal_id,script,candidate_parser=_shu_queue_candidates) if is_shu else _kor_source_binding(journal_id,script) if (is_kor or is_nqg) else source_binding(journal_id,script)
        edits=[]
        for branch_index, group in branches_by_journal.get(journal_id,{}).items():
            branch=binding["branches"][branch_index]
            node,limit,trigger=_branch_node(script,branch)
            turns=" OR = { "+" ".join(f"{turn(c)} = yes" for c in group)+" }"
            reserve_calls=" ".join(f"if = {{ limit = {{ {turn(c)} = yes }} {prefix}_reserve_{c['id']} = yes }}" for c in group)
            if is_kor or (is_nqg and any(c.get("nqg_aid_notice") for c in group)):
                if any(c.get("kor_instructor_notice") for c in group):
                    if len(group) != 1 or not group[0].get("kor_instructor_notice"):
                        raise ValueError("KOR instructor notice sender must own one exact candidate")
                    c = group[0]
                    f = _kor_instructor_fields(c["id"])
                    gate = [f"var:{reservation} = {c['id']}", f"has_variable = {epoch}",
                            f"var:{epoch} > 0", f"has_variable = {prefix}_candidate_epoch_{c['id']}",
                            f"var:{prefix}_candidate_epoch_{c['id']} = var:{epoch}"]
                    gate.extend(_kor_instructor_checks(c["id"], delivered=False))
                    exports = ["save_scope_as = ywc_kor_notice_owner"]
                    for suffix in ("serial", "generation", "request_state", "reason", "partner_available"):
                        exports.append(f"save_scope_value_as = {{ name = ywc_kor_notice_{suffix} value = var:{f[suffix]} }}")
                    exports += [f"save_scope_value_as = {{ name = ywc_kor_notice_candidate value = var:{reservation} }}",
                                f"save_scope_value_as = {{ name = ywc_kor_notice_epoch value = var:{epoch} }}",
                                f"if = {{ limit = {{ var:{f['partner_available']} = 1 exists = var:{f['partner']} }} "
                                f"var:{f['partner']} = {{ save_scope_as = ywc_kor_notice_partner }} }}"]
                    wrapped = (f"if = {{ limit = {{ {turns} }} {reserve_calls} "
                               f"if = {{ limit = {{ {' '.join(gate)} }} {' '.join(exports)} {render_node(trigger, script)} }} }}")
                elif any(c.get("kor_procurement_notice") for c in group):
                    if len(group) != 1 or not group[0].get("kor_procurement_notice"):
                        raise ValueError("KOR procurement notice sender must own one exact candidate")
                    c = group[0]
                    f = _kor_procurement_fields(c["id"])
                    gate = [f"var:{reservation} = {c['id']}", f"has_variable = {epoch}",
                            f"var:{epoch} > 0", f"has_variable = {prefix}_candidate_epoch_{c['id']}",
                            f"var:{prefix}_candidate_epoch_{c['id']} = var:{epoch}"]
                    gate.extend(_kor_procurement_checks(c["id"], delivered=False))
                    exports = ["save_scope_as = ywc_kor_procurement_notice_owner"]
                    for suffix in ("serial", "generation", "request_state", "reason", "partner_available"):
                        exports.append(f"save_scope_value_as = {{ name = ywc_kor_procurement_notice_{suffix} value = var:{f[suffix]} }}")
                    exports += [f"save_scope_value_as = {{ name = ywc_kor_procurement_notice_candidate value = var:{reservation} }}",
                                f"save_scope_value_as = {{ name = ywc_kor_procurement_notice_epoch value = var:{epoch} }}",
                                f"if = {{ limit = {{ var:{f['partner_available']} = 1 exists = var:{f['partner']} }} "
                                f"var:{f['partner']} = {{ save_scope_as = ywc_kor_procurement_notice_partner }} }}"]
                    wrapped = (f"if = {{ limit = {{ {turns} }} {reserve_calls} "
                               f"if = {{ limit = {{ {' '.join(gate)} }} {' '.join(exports)} {render_node(trigger, script)} }} }}")
                elif any(c.get("nqg_aid_notice") for c in group):
                    if len(group) != 1 or not group[0].get("nqg_aid_notice"):
                        raise ValueError("NQG aid notice sender must own one exact candidate")
                    c = group[0]
                    f = _nqg_aid_fields(c["id"])
                    gate = [f"var:{reservation} = {c['id']}", f"has_variable = {epoch}",
                            f"var:{epoch} > 0", f"has_variable = {prefix}_candidate_epoch_{c['id']}",
                            f"var:{prefix}_candidate_epoch_{c['id']} = var:{epoch}"]
                    gate.extend(_nqg_aid_checks(c["id"], delivered=False))
                    exports = ["save_scope_as = ywc_nqg_winter_aid_notice_owner"]
                    for suffix in ("serial", "generation", "request_state", "reason", "partner_available"):
                        exports.append(f"save_scope_value_as = {{ name = ywc_nqg_winter_aid_notice_{suffix} value = var:{f[suffix]} }}")
                    exports += [f"save_scope_value_as = {{ name = ywc_nqg_winter_aid_notice_candidate value = var:{reservation} }}",
                                f"save_scope_value_as = {{ name = ywc_nqg_winter_aid_notice_epoch value = var:{epoch} }}",
                                f"if = {{ limit = {{ var:{f['partner_available']} = 1 exists = var:{f['partner']} }} "
                                f"var:{f['partner']} = {{ save_scope_as = ywc_nqg_winter_aid_notice_partner }} }}"]
                    wrapped = (f"if = {{ limit = {{ {turns} }} {reserve_calls} "
                               f"if = {{ limit = {{ {' '.join(gate)} }} {' '.join(exports)} {render_node(trigger, script)} }} }}")
                else:
                    wrapped = f"if = {{ limit = {{ {turns} }} {reserve_calls} {render_node(trigger, script)} }}"
                edits.append((trigger.start, trigger.end, wrapped))
            else:
                edits.append((branch["limit_end"]-1,branch["limit_end"]-1," "+turns+" "))
                edits.append((branch["limit_end"],branch["limit_end"]," "+reserve_calls+" "))
            # The source queue removal moves to post-immediate ACK so failed trigger attempts remain retryable.
            for op in children(node):
                if op.key=="remove_variable" and isinstance(op.value,str) and any(op.value==c["queue"]["queue"] for c in group):
                    edits.append((op.start,op.end,""))
        for start,end,replacement in sorted(edits,reverse=True): script=script[:start]+replacement+script[end:]
        # Ensure scheduler state and reservation expiry are refreshed once in each native JE pulse.
        monthly=direct_values(parse_block(script),"on_monthly_pulse")[0]
        pulse=direct_values(children(monthly),"effect")[0]
        prepare = f" {prefix}_prepare = yes\n" if is_nmg else f" {prefix}_prepare = yes "
        script=script[:pulse.value_start+1]+prepare+script[pulse.value_start+1:]
        if is_kor or is_shu:
            script = re.sub(r"[ \t]+(?=\r?\n)", "", script)
        journal_scripts[journal_id]=script
    event_hooks={}; ack_hooks={}
    for event_id, group in candidates_by_event.items():
        event_hooks[event_id]=[dispatch(c) for c in group]
        hooks=[]
        for c in group:
            hooks.append(f"{prefix}_callback_{c['id']}" if (is_kor or is_nqg or is_shu or is_lan or is_nmg or is_mgl) else f"ywc_v03_dmg_inline_ack_{c['id']}")
        ack_hooks[event_id]=hooks
    inline_proofs={}
    if is_supported_inline_country:
        for event_id, group in candidates_by_event.items():
            proofs=[]
            for c in group:
                ident=c["id"]; qvar=c["queue"]["queue"]; sp=_queue_snapshot_name(ident,qvar,"present",prefix); sv=_queue_snapshot_name(ident,qvar,"value",prefix)
                proof=f"{prefix}_callback_{ident}"; cidvar=f"{prefix}_callback_candidate_{ident}"; epvar=f"{prefix}_callback_epoch_{ident}"; qproof=f"{prefix}_callback_queue_{ident}"
                checks=[f"var:{reservation} = {ident}",f"has_variable = {timer}",f"has_variable = {epoch}",f"has_variable = {prefix}_candidate_epoch_{ident}",f"var:{epoch} > 0",f"var:{prefix}_candidate_epoch_{ident} = var:{epoch}",f"has_variable = {sp}",f"has_variable = {sv}",f"has_journal_entry = {c['journal']['id']}",f"has_variable = {c['phase']['live_witness']}"]
                if is_lan:
                    checks += [f"has_variable = {prefix}_body_completed_{ident}",f"var:{prefix}_body_completed_{ident} = 1",f"has_variable = {prefix}_body_completed_epoch_{ident}",f"var:{prefix}_body_completed_epoch_{ident} = var:{epoch}"]
                if is_mgl:
                    checks += [f"has_variable = {prefix}_body_completed_{ident}",
                               f"var:{prefix}_body_completed_{ident} = 1",
                               f"has_variable = {prefix}_body_completed_epoch_{ident}",
                               f"var:{prefix}_body_completed_epoch_{ident} = var:{epoch}"]
                if is_shu:
                    checks += [f"has_variable = {qvar}",f"var:{qvar} = var:{sv}",f"NOT = {{ var:{served[c['arc']['slug']]} = var:{roundv} }}"]
                else:
                    checks.append(f"NOT = {{ var:{served[c['arc']['slug']]} = var:{roundv} }}")
                    consumed = _dmg_native_notice_consumption(c) if is_dmg else None
                    if consumed:
                        checks.append("OR = { AND = { has_variable = " + qvar + f" var:{qvar} = var:{sv} }} {consumed} }}")
                    else:
                        checks += [f"has_variable = {qvar}",f"var:{qvar} = var:{sv}"]
                if is_nqg:
                    calls_notice_helper = _nqg_event_calls_notice_helper(c["event"], c["arc"]["slug"])
                    if c["queue"]["kind"] in {"notice12", "notice36"}:
                        if not calls_notice_helper:
                            raise ValueError(f"{c['event']['id']}: notice candidate has no native notice delivery helper")
                        checks.extend([f"NOT = {{ has_variable = {c['intent_variable']} }}",
                                       f"has_variable = {c['receipt_variable']}",
                                       f"var:{c['receipt_variable']} = 1",
                                       f"has_variable = {c['open_variable']}",
                                       f"var:{c['open_variable']} = 1"])
                    elif calls_notice_helper:
                        base = {"v03_nqg_winter_court": "winter", "v03_nqg_hunting_rights": "hunting", "v03_nqg_northern_port": "port"}[c["arc"]["slug"]]
                        checks.extend([f"NOT = {{ has_variable = ywc_nqg_{base}_notice12_intent }}",
                                       f"NOT = {{ has_variable = ywc_nqg_{base}_notice36_intent }}"])
                    for name in _nqg_candidate_state(c, candidates):
                        if name in {c.get("intent_variable"), c.get("receipt_variable"), c.get("open_variable")}:
                            continue
                        present = _queue_snapshot_name(ident, name, "present", prefix)
                        value = _queue_snapshot_name(ident, name, "value", prefix)
                        checks.append("OR = { "
                            f"AND = {{ has_variable = {present} has_variable = {value} has_variable = {name} var:{name} = var:{value} }} "
                            f"AND = {{ NOT = {{ has_variable = {present} }} NOT = {{ has_variable = {value} }} NOT = {{ has_variable = {name} }} }} }}")
                elif c.get("receipt_variable") and type(c.get("receipt_value")) is int:
                    checks += [f"has_variable = {c['receipt_variable']}", f"var:{c['receipt_variable']} = {c['receipt_value']}"]
                if is_nmg:
                    checks += _nmg_native_postchecks(c, prefix)
                if is_mgl:
                    checks.extend(_mgl_snapshot_checks(c, prefix))
                if c["queue"]["mode"]=="exact": checks.append(f"var:{sv} = {c['queue']['value']}")
                if c.get("kor_instructor_notice"):
                    f = _kor_instructor_fields(ident)
                    checks.extend(_kor_instructor_checks(ident, delivered=True))
                    checks += ["has_variable = ywc_kor_instructor_notice_open_serial",
                               "var:ywc_kor_instructor_notice_open_serial = scope:ywc_kor_notice_serial"]
                if c.get("kor_procurement_notice"):
                    f = _kor_procurement_fields(ident)
                    checks.extend(_kor_procurement_checks(ident, delivered=True))
                    checks += ["has_variable = ywc_kor_procurement_notice_open_serial",
                               "var:ywc_kor_procurement_notice_open_serial = scope:ywc_kor_procurement_notice_serial"]
                if c.get("nqg_aid_notice"):
                    f = _nqg_aid_fields(ident)
                    checks.extend(_nqg_aid_checks(ident, delivered=True))
                    checks += ["has_variable = ywc_nqg_winter_aid_notice_open_serial",
                               "var:ywc_nqg_winter_aid_notice_open_serial = scope:ywc_nqg_winter_aid_notice_serial"]
                if is_lan:
                    stem=qvar.split("_")[2]; queue=c["queue"]
                    tracked=[f"ywc_lan_{stem}_notice_current",f"ywc_lan_{stem}_notice12_sent",f"ywc_lan_{stem}_notice36_sent",f"ywc_lan_{stem}_pending_event",f"ywc_lan_{stem}_notice_event"]
                    for name in dict.fromkeys(tracked):
                        if queue["kind"] == "notice" and name in {f"ywc_lan_{stem}_notice_current",f"ywc_lan_{stem}_notice{queue['value']}_sent"}:
                            post=str(queue["value"]) if name.endswith("notice_current") else "1"
                            checks += [f"has_variable = {name}",f"var:{name} = {post}"]
                            continue
                        pv=_queue_snapshot_name(ident,name,"present",prefix); vv=_queue_snapshot_name(ident,name,"value",prefix)
                        checks.append("OR = { "+f"AND = {{ has_variable = {pv} has_variable = {vv} var:{pv} = 1 has_variable = {name} var:{name} = var:{vv} }} "+f"AND = {{ has_variable = {pv} has_variable = {vv} var:{pv} = 0 var:{vv} = 0 NOT = {{ has_variable = {name} }} }} }}")
                queue_proof_value = f"var:{qvar}" if is_shu else f"var:{sv}"
                if is_lan:
                    # The outer guarded immediate already admitted one unique candidate.
                    # After the complete native body, reservation identity alone must
                    # disarm rollback even if a native/fault boundary removed timer or
                    # epochs. Completion inhibits rollback only; ACK still checks epochs.
                    completion = f"if = {{ limit = {{ var:{reservation} = {ident} }} set_variable = {{ name = {prefix}_body_completed_{ident} value = 1 }} if = {{ limit = {{ has_variable = {prefix}_candidate_epoch_{ident} }} set_variable = {{ name = {prefix}_body_completed_epoch_{ident} value = var:{prefix}_candidate_epoch_{ident} }} }} remove_variable = {prefix}_rollback_armed_{ident} }}"
                    proof_body=f"{completion} if = {{ limit = {{ {' '.join(checks)} }} set_variable = {{ name = {proof} value = 1 }} set_variable = {{ name = {cidvar} value = {ident} }} set_variable = {{ name = {epvar} value = var:{epoch} }} set_variable = {{ name = {qproof} value = {queue_proof_value} }} }}"
                    proofs.append(proof_body)
                elif c.get("kor_instructor_notice"):
                    f = _kor_instructor_fields(ident)
                    completion_checks = [f"var:{reservation} = {ident}",
                                         f"has_variable = {epoch}",
                                         f"has_variable = {prefix}_candidate_epoch_{ident}",
                                         f"var:{prefix}_candidate_epoch_{ident} = var:{epoch}",
                                         f"scope:ywc_kor_notice_candidate ?= {ident}",
                                         f"scope:ywc_kor_notice_epoch ?= var:{epoch}",
                                         "ywc_kor_instructor_notice_live = yes",
                                         "scope:ywc_kor_notice_serial ?= var:ywc_kor_instructor_notice_serial",
                                         "var:ywc_kor_instructor_notice_open_serial = scope:ywc_kor_notice_serial"]
                    completion = (f"if = {{ limit = {{ {' '.join(completion_checks)} }} "
                                  f"set_variable = {{ name = {f['body_completed']} value = 1 }} "
                                  f"set_variable = {{ name = {f['body_completed_epoch']} value = var:{epoch} }} "
                                  f"set_variable = {{ name = {f['body_completed_serial']} value = scope:ywc_kor_notice_serial }} }}")
                    proof_checks = checks + [f"has_variable = {f['body_completed']}",
                                             f"var:{f['body_completed']} = 1",
                                             f"var:{f['body_completed_epoch']} = var:{epoch}",
                                             f"var:{f['body_completed_serial']} = scope:ywc_kor_notice_serial"]
                    proofs.append(f"{completion} if = {{ limit = {{ {' '.join(proof_checks)} }} "
                                  f"set_variable = {{ name = {proof} value = 1 }} "
                                  f"set_variable = {{ name = {cidvar} value = {ident} }} "
                                  f"set_variable = {{ name = {epvar} value = var:{epoch} }} "
                                  f"set_variable = {{ name = {qproof} value = {queue_proof_value} }} }}")
                elif c.get("kor_procurement_notice"):
                    f = _kor_procurement_fields(ident)
                    completion_checks = [f"var:{reservation} = {ident}",
                                         f"has_variable = {epoch}",
                                         f"has_variable = {prefix}_candidate_epoch_{ident}",
                                         f"var:{prefix}_candidate_epoch_{ident} = var:{epoch}",
                                         f"scope:ywc_kor_procurement_notice_candidate ?= {ident}",
                                         f"scope:ywc_kor_procurement_notice_epoch ?= var:{epoch}",
                                         "ywc_kor_procurement_notice_live = yes",
                                         "scope:ywc_kor_procurement_notice_serial ?= var:ywc_kor_procurement_notice_serial",
                                         "var:ywc_kor_procurement_notice_open_serial = scope:ywc_kor_procurement_notice_serial"]
                    completion = (f"if = {{ limit = {{ {' '.join(completion_checks)} }} "
                                  f"set_variable = {{ name = {f['body_completed']} value = 1 }} "
                                  f"set_variable = {{ name = {f['body_completed_epoch']} value = var:{epoch} }} "
                                  f"set_variable = {{ name = {f['body_completed_serial']} value = scope:ywc_kor_procurement_notice_serial }} }}")
                    proof_checks = checks + [f"has_variable = {f['body_completed']}",
                                             f"var:{f['body_completed']} = 1",
                                             f"var:{f['body_completed_epoch']} = var:{epoch}",
                                             f"var:{f['body_completed_serial']} = scope:ywc_kor_procurement_notice_serial"]
                    proofs.append(f"{completion} if = {{ limit = {{ {' '.join(proof_checks)} }} "
                                  f"set_variable = {{ name = {proof} value = 1 }} "
                                  f"set_variable = {{ name = {cidvar} value = {ident} }} "
                                  f"set_variable = {{ name = {epvar} value = var:{epoch} }} "
                                  f"set_variable = {{ name = {qproof} value = {queue_proof_value} }} }}")
                elif c.get("nqg_aid_notice"):
                    f = _nqg_aid_fields(ident)
                    completion_checks = [f"var:{reservation} = {ident}",
                                         f"has_variable = {epoch}",
                                         f"has_variable = {prefix}_candidate_epoch_{ident}",
                                         f"var:{prefix}_candidate_epoch_{ident} = var:{epoch}",
                                         f"scope:ywc_nqg_winter_aid_notice_candidate ?= {ident}",
                                         f"scope:ywc_nqg_winter_aid_notice_epoch ?= var:{epoch}",
                                         "ywc_nqg_winter_aid_notice_live = yes",
                                         "scope:ywc_nqg_winter_aid_notice_serial ?= var:ywc_nqg_winter_aid_notice_serial",
                                         "var:ywc_nqg_winter_aid_notice_open_serial = scope:ywc_nqg_winter_aid_notice_serial"]
                    completion = (f"if = {{ limit = {{ {' '.join(completion_checks)} }} "
                                  f"set_variable = {{ name = {f['body_completed']} value = 1 }} "
                                  f"set_variable = {{ name = {f['body_completed_epoch']} value = var:{epoch} }} "
                                  f"set_variable = {{ name = {f['body_completed_serial']} value = scope:ywc_nqg_winter_aid_notice_serial }} }}")
                    proof_checks = checks + [f"has_variable = {f['body_completed']}",
                                             f"var:{f['body_completed']} = 1",
                                             f"var:{f['body_completed_epoch']} = var:{epoch}",
                                             f"var:{f['body_completed_serial']} = scope:ywc_nqg_winter_aid_notice_serial"]
                    proofs.append(f"{completion} if = {{ limit = {{ {' '.join(proof_checks)} }} "
                                  f"set_variable = {{ name = {proof} value = 1 }} "
                                  f"set_variable = {{ name = {cidvar} value = {ident} }} "
                                  f"set_variable = {{ name = {epvar} value = var:{epoch} }} "
                                  f"set_variable = {{ name = {qproof} value = {queue_proof_value} }} }}")
                elif is_nmg or is_mgl:
                    completion = (f"if = {{ limit = {{ var:{reservation} = {ident} }} "
                                  f"set_variable = {{ name = {prefix}_body_completed_{ident} value = 1 }} "
                                  f"set_variable = {{ name = {prefix}_body_completed_epoch_{ident} value = var:{prefix}_candidate_epoch_{ident} }} }}")
                    proof_body=f"{completion} if = {{ limit = {{ {' '.join(checks)} }} set_variable = {{ name = {proof} value = 1 }} set_variable = {{ name = {cidvar} value = {ident} }} set_variable = {{ name = {epvar} value = var:{epoch} }} set_variable = {{ name = {qproof} value = {queue_proof_value} }} }}"
                    proofs.append(proof_body)
                else:
                    proofs.append(f"if = {{ limit = {{ {' '.join(checks)} }} set_variable = {{ name = {proof} value = 1 }} set_variable = {{ name = {cidvar} value = {ident} }} set_variable = {{ name = {epvar} value = var:{epoch} }} set_variable = {{ name = {qproof} value = {queue_proof_value} }} }}")
            inline_proofs[event_id]=proofs
    return {"triggers":"\n\n".join(triggers)+"\n","effects":"\n\n".join(effects)+"\n","event_hooks":event_hooks,"ack_hooks":ack_hooks,"inline_proofs":inline_proofs,"guarded_immediate_events":sorted(event_hooks),"journal_scripts":journal_scripts,"live_witnesses":{j:p["phase"]["live_witness"] for j,p in phases.items()},"mgl_safe_comment_boundaries":is_mgl}


def validate_tib_native_helper_source(effects_source: str, triggers_source: str) -> None:
    """Validate the complete native TIB helper ABI supplied by the caller."""
    try:
        from tools.v03_tib_inline_delivery_adapter import validate_tib_native_helper_source as validate
    except ModuleNotFoundError:
        from v03_tib_inline_delivery_adapter import validate_tib_native_helper_source as validate
    validate(effects_source, triggers_source)
