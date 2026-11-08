"""Source-bound inline delivery adapter for the three JHG foundation arcs.

JHG keeps its authored monthly business logic intact. This module only adds a
private, per-invocation delivery protocol around those already-owned branches.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any

PREFIX = "ywc_v03_jhg_inline"
SCHEMA = "v03.foundation_inline_adapter.v2"
EXPECTED_ARCS = {
    "v03_jhg_court_assembly",
    "v03_jhg_convoy_capacity",
    "v03_jhg_tribute_autonomy",
}
EFFECTS_AST_SHA256 = "dd50a96e65591e2f79abf657fbc94ca00a5479237db0fbc165cb41b1e34aeab7"
TRIGGERS_AST_SHA256 = "f20895a3fe05a8a13b1c9b24111380e462442962e61ed6f9692283e0a5cb7aa0"


def _int_tree(value: Any, where: str = "metadata") -> None:
    if isinstance(value, bool) or isinstance(value, float):
        raise ValueError(f"{where}: Boolean and floating point aliases are not accepted")
    if isinstance(value, dict):
        for key, item in value.items():
            _int_tree(item, f"{where}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _int_tree(item, f"{where}[{index}]")


def _queue_candidates(branch_source: str) -> list[dict[str, Any]]:
    try:
        from tools.v03_inline_delivery_adapter import children, direct_values, parse_block
    except ModuleNotFoundError:
        from v03_inline_delivery_adapter import children, direct_values, parse_block

    roots = parse_block("{ " + branch_source + " }")
    if len(roots) != 1 or roots[0].key not in {"if", "else_if"}:
        raise ValueError("JHG source site must be one if/else_if branch")
    limits = direct_values(children(roots[0]), "limit")
    events = direct_values(children(roots[0]), "trigger_event")
    if len(limits) != 1 or len(events) != 1:
        raise ValueError("JHG sender branch needs one direct limit and event")
    found: list[dict[str, Any]] = []

    def walk(nodes: tuple[Any, ...], excluded: bool = False) -> None:
        for node in nodes:
            neg = excluded or node.key == "NOT"
            if isinstance(node.value, tuple):
                if node.key in {"OR", "XOR", "NOR"}:
                    raise ValueError(f"JHG sender contains unsupported queue Boolean {node.key}")
                walk(node.value, neg)
            elif not neg and node.key.startswith("var:ywc_jhg_") and node.op == "=" and isinstance(node.value, str) and node.value.isdigit():
                queue = node.key[4:]
                if queue.endswith(("_pending_event", "_notice_pending_event")):
                    found.append({"queue": queue, "kind": "notice" if queue.endswith("_notice_pending_event") else "normal",
                                  "mode": "exact", "value": int(node.value)})
    walk(children(limits[0]))
    if len(found) != 1:
        raise ValueError(f"JHG sender must bind one positive exact native queue; got {found!r}")
    return found


def _binding(journal_id: str, script: str) -> list[dict[str, Any]]:
    try:
        from tools.v03_inline_delivery_adapter import _kor_source_binding, children, direct_values, parse_block
    except ModuleNotFoundError:
        from v03_inline_delivery_adapter import _kor_source_binding, children, direct_values, parse_block

    bound = _kor_source_binding(journal_id, script, candidate_parser=_queue_candidates,
                                exclusion_parser=lambda _source: [])
    top = parse_block(script)
    monthly = direct_values(top, "on_monthly_pulse")
    if len(monthly) != 1:
        raise ValueError(f"{journal_id}: JHG requires one monthly pulse")
    effects = direct_values(children(monthly[0]), "effect")
    if len(effects) != 1:
        raise ValueError(f"{journal_id}: JHG monthly pulse needs one effect block")
    nodes = children(effects[0])
    chain_at: dict[int, int] = {}
    chain = -1
    in_chain = False
    for ordinal, node in enumerate(nodes):
        if node.key == "if":
            chain += 1
            in_chain = True
        elif node.key in {"else_if", "else"} and in_chain:
            pass
        else:
            in_chain = False
        if node.key in {"if", "else_if", "else"} and in_chain:
            chain_at[ordinal] = chain
    result = []
    for row in bound["branches"]:
        node = next((n for n in nodes if n.start == row["start"] and n.end == row["end"]), None)
        if node is None:
            raise ValueError(f"{journal_id}: JHG sender AST binding lost")
        ordinal = nodes.index(node)
        if ordinal not in chain_at:
            raise ValueError(f"{journal_id}: JHG sender is outside an authored branch chain")
        result.append({**row, "statement_ordinal": ordinal, "chain_index": chain_at[ordinal],
                       "branch_kind": node.key, "candidates": _queue_candidates(script[node.start:node.end]),
                       "queue_exclusions": []})
    return result


def _source_rows(catalog: dict[str, Any]) -> list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]]:
    try:
        from tools.v03_inline_delivery_adapter import _kor_direct_adds
    except ModuleNotFoundError:
        from v03_inline_delivery_adapter import _kor_direct_adds

    rows = []
    for arc in catalog["arcs"]:
        for journal in arc["journals"]:
            for branch in _binding(journal["id"], journal["script"]):
                rows.append((arc, journal, branch))
    return rows


def annotate_jhg_catalog(catalog: dict[str, Any]) -> dict[str, Any]:
    """Return strict v2 bindings derived from each complete raw source AST."""
    try:
        from tools.v03_inline_delivery_adapter import _kor_direct_adds
    except ModuleNotFoundError:
        from v03_inline_delivery_adapter import _kor_direct_adds

    import copy
    result = copy.deepcopy(catalog)
    for arc in result["arcs"]:
        phases = []
        branches = []
        for journal in arc["journals"]:
            suffix = journal["id"].removeprefix("ywc_je_v03_jhg_")
            phases.append({"journal": journal["id"], "live_witness": f"{PREFIX}_live_{suffix}",
                           "source_script_sha256": hashlib.sha256(journal["script"].encode("utf-8")).hexdigest(),
                           "goal_sha256": hashlib.sha256(journal["goal"].encode("utf-8")).hexdigest(),
                           "exit_sha256": hashlib.sha256(journal["exit_conditions"].encode("utf-8")).hexdigest()})
            for row in _binding(journal["id"], journal["script"]):
                branches.append({"journal": journal["id"], **{key: row[key] for key in (
                    "branch_index", "statement_ordinal", "chain_index", "branch_kind", "event")},
                    "branch_sha256": row["sha256"], "limit_sha256": row["limit_sha256"],
                    "chain_prior": row["chain_prior"], "chain_sha256": row["chain_sha256"],
                    "candidates": row["candidates"], "queue_exclusions": row["queue_exclusions"]})
        arc["inline_delivery_adapter"] = {"schema": SCHEMA, "live_phases": phases,
            "branches": branches, "direct_adds": _kor_direct_adds(arc)}
    return result


def validate_jhg_native_helper_source(effects_source: str, triggers_source: str) -> None:
    """Reject duplicate or AST-drifted native JHG helper definitions."""
    try:
        from tools.v03_inline_delivery_adapter import parse_block
    except ModuleNotFoundError:
        from v03_inline_delivery_adapter import parse_block

    for label, source, expected in (("effects", effects_source, EFFECTS_AST_SHA256),
                                    ("triggers", triggers_source, TRIGGERS_AST_SHA256)):
        try:
            nodes = parse_block("{\n" + source + "\n}")
        except Exception as exc:
            raise ValueError(f"JHG native helper {label} source is not parseable: {exc}") from exc
        names = [node.key for node in nodes]
        if len(names) != len(set(names)):
            raise ValueError(f"JHG native helper {label} source contains duplicate definitions")
        def canonical(node: Any) -> tuple[Any, ...]:
            value = [canonical(child) for child in node.value] if isinstance(node.value, tuple) else node.value
            return node.key, node.op, value
        digest = hashlib.sha256(repr([canonical(node) for node in nodes]).encode("utf-8")).hexdigest()
        if digest != expected:
            raise ValueError(f"JHG native helper {label} source ABI/AST drift")


def _validate_catalog(catalog: dict[str, Any]) -> None:
    try:
        from tools.v03_inline_delivery_adapter import _kor_direct_adds
    except ModuleNotFoundError:
        from v03_inline_delivery_adapter import _kor_direct_adds

    if not isinstance(catalog, dict) or catalog.get("key") != "country_jhg":
        raise ValueError("JHG inline adapter requires the JHG catalog")
    arcs = catalog.get("arcs")
    if not isinstance(arcs, list):
        raise ValueError("JHG inline adapter requires three foundation arcs")
    selected = [arc for arc in arcs if isinstance(arc, dict) and arc.get("era") == "foundation"]
    if len(selected) != 3 or {arc.get("slug") for arc in selected} != EXPECTED_ARCS:
        raise ValueError("JHG inline adapter requires exactly its three foundation arcs")
    witnesses: set[str] = set()
    all_events: set[str] = set()
    branches_seen: set[tuple[str, int]] = set()
    bindings_seen: set[tuple[str, str, str, int]] = set()
    all_sources = []
    for arc in selected:
        adapter = arc.get("inline_delivery_adapter")
        if not isinstance(adapter, dict) or set(adapter) != {"schema", "live_phases", "branches", "direct_adds"} or adapter.get("schema") != SCHEMA:
            raise ValueError(f"{arc.get('slug')}: strict v2 inline metadata required")
        _int_tree(adapter, arc.get("slug", "arc"))
        journals = arc.get("journals")
        events = arc.get("events")
        expected_counts = {"v03_jhg_court_assembly": (2, 8), "v03_jhg_convoy_capacity": (3, 10),
                           "v03_jhg_tribute_autonomy": (1, 6)}[arc["slug"]]
        if not isinstance(journals, list) or len(journals) != expected_counts[0] or not isinstance(events, list) or len(events) != expected_counts[1]:
            raise ValueError(f"{arc['slug']}: JHG journal/event inventory drift")
        phases = adapter["live_phases"]
        if not isinstance(phases, list) or len(phases) != len(journals):
            raise ValueError(f"{arc['slug']}: every native JE needs one phase witness")
        for phase, journal in zip(phases, journals):
            required = {"journal", "live_witness", "source_script_sha256", "goal_sha256", "exit_sha256"}
            if not isinstance(phase, dict) or set(phase) != required or phase["journal"] != journal["id"]:
                raise ValueError(f"{arc['slug']}: malformed JHG phase binding")
            for field, source_field in (("source_script_sha256", "script"), ("goal_sha256", "goal"), ("exit_sha256", "exit_conditions")):
                digest = hashlib.sha256(journal[source_field].encode("utf-8")).hexdigest()
                if type(phase[field]) is not str or phase[field] != digest:
                    raise ValueError(f"{journal['id']}: JHG source {source_field} drift")
            witness = phase["live_witness"]
            if type(witness) is not str or not re.fullmatch(PREFIX + r"_live_[a-z0-9_]+", witness) or witness in witnesses:
                raise ValueError(f"{journal['id']}: invalid or duplicate JHG live witness")
            witnesses.add(witness)
        if adapter["direct_adds"] != _kor_direct_adds(arc):
            raise ValueError(f"{arc['slug']}: JHG direct-add binding drift")
        for event in events:
            event_id = event.get("id") if isinstance(event, dict) else None
            if not isinstance(event_id, str) or event_id in all_events:
                raise ValueError(f"{arc['slug']}: duplicate or invalid JHG event identity")
            all_events.add(event_id)
            immediate = event.get("immediate")
            if type(immediate) is not str:
                raise ValueError(f"{event_id}: native immediate must remain raw source text")
            try:
                from tools.v03_inline_delivery_adapter import parse_block
            except ModuleNotFoundError:
                from v03_inline_delivery_adapter import parse_block
            body = parse_block(immediate)
            if len(body) != 1 or body[0].key != "ywc_v03_mark_major_delivered" or body[0].op != "=" or body[0].value != "yes":
                raise ValueError(f"{event_id}: native immediate layout drift")
        expected_rows = []
        for journal in journals:
            expected_rows.extend((journal["id"], row) for row in _binding(journal["id"], journal["script"]))
        records = adapter["branches"]
        if not isinstance(records, list) or len(records) != len(expected_rows):
            raise ValueError(f"{arc['slug']}: all JHG native sender branches must be bound")
        required = {"journal", "branch_index", "statement_ordinal", "chain_index", "branch_kind", "event",
                    "branch_sha256", "limit_sha256", "chain_prior", "chain_sha256", "candidates", "queue_exclusions"}
        for proof, (jid, source) in zip(records, expected_rows):
            if not isinstance(proof, dict) or set(proof) != required:
                raise ValueError(f"{arc['slug']}/{jid}: malformed JHG source binding")
            checks = {"journal": jid, "branch_index": source["branch_index"],
                      "statement_ordinal": source["statement_ordinal"], "chain_index": source["chain_index"],
                      "branch_kind": source["branch_kind"], "event": source["event"],
                      "branch_sha256": source["sha256"], "limit_sha256": source["limit_sha256"],
                      "chain_prior": source["chain_prior"], "chain_sha256": source["chain_sha256"],
                      "candidates": source["candidates"], "queue_exclusions": source["queue_exclusions"]}
            if any(proof.get(field) != expected for field, expected in checks.items()):
                raise ValueError(f"{arc['slug']}/{jid}: raw JHG branch, priority chain or queue drift")
            for key in ("branch_index", "statement_ordinal", "chain_index"):
                if type(proof[key]) is not int:
                    raise ValueError(f"{jid}: {key} must be an integer")
            identity = (jid, proof["branch_index"])
            if identity in branches_seen:
                raise ValueError(f"{jid}: duplicate JHG branch identity")
            branches_seen.add(identity)
            candidate = proof["candidates"][0]
            if (not isinstance(candidate, dict) or set(candidate) != {"queue", "kind", "mode", "value"}
                or type(candidate["value"]) is not int or candidate["mode"] != "exact"
                or candidate["kind"] not in {"normal", "notice"}):
                raise ValueError(f"{jid}: malformed JHG queue candidate")
            binding_identity = (proof["event"], jid, candidate["queue"], candidate["value"])
            if binding_identity in bindings_seen:
                raise ValueError(f"{jid}: duplicate JHG event/queue binding")
            bindings_seen.add(binding_identity)
            all_sources.append((arc, next(j for j in journals if j["id"] == jid), proof))
    if len(witnesses) != 6 or len(all_events) != 24 or len(all_sources) != 58:
        raise ValueError("JHG adapter must bind six phases, 24 events and 58 source senders")
    if sum(row[2]["candidates"][0]["kind"] == "normal" for row in all_sources) != 52:
        raise ValueError("JHG adapter must bind 52 normal and six notice senders")


def _ast_rows(nodes: Any) -> list[tuple[Any, ...]]:
    try:
        from tools.v03_inline_delivery_adapter import children
    except ModuleNotFoundError:
        from v03_inline_delivery_adapter import children
    return [(node.key, node.op, _ast_rows(children(node)) if isinstance(node.value, tuple) else node.value) for node in nodes]


def _node_refs(nodes: Any) -> set[str]:
    try:
        from tools.v03_inline_delivery_adapter import children
    except ModuleNotFoundError:
        from v03_inline_delivery_adapter import children
    refs: set[str] = set()
    for node in nodes:
        if node.key.startswith("var:ywc_jhg_"):
            refs.add(node.key[4:])
        elif node.key == "has_variable" and isinstance(node.value, str) and node.value.startswith("ywc_jhg_"):
            refs.add(node.value)
        elif node.key == "remove_variable" and isinstance(node.value, str) and node.value.startswith("ywc_jhg_"):
            refs.add(node.value)
        elif node.key in {"set_variable", "change_variable", "clamp_variable"} and isinstance(node.value, tuple):
            refs.update(child.value for child in children(node) if child.key == "name" and isinstance(child.value, str) and child.value.startswith("ywc_jhg_"))
        if isinstance(node.value, tuple):
            refs.update(_node_refs(children(node)))
    return refs


def _render_adapter(catalog: dict[str, Any]) -> dict[str, Any]:
    try:
        from tools.v03_inline_delivery_adapter import children, direct_values, parse_block, render_node
    except ModuleNotFoundError:
        from v03_inline_delivery_adapter import children, direct_values, parse_block, render_node
    _validate_catalog(catalog)
    arcs = [a for a in catalog["arcs"] if a.get("era") == "foundation"]
    native_queues = {
        candidate["queue"]
        for arc in arcs for journal in arc["journals"]
        for branch in _binding(journal["id"], journal["script"])
        for candidate in branch["candidates"]
    }
    native_stems = {
        queue.removesuffix("_notice_pending_event").removesuffix("_pending_event")
        for queue in native_queues
    }
    rows: list[dict[str, Any]] = []
    live: dict[str, str] = {}
    journal_scripts: dict[str, str] = {}
    for arc in arcs:
        for phase in arc["inline_delivery_adapter"]["live_phases"]:
            live[phase["journal"]] = phase["live_witness"]
        for journal in arc["journals"]:
            branches = _binding(journal["id"], journal["script"])
            script = journal["script"]
            updates = []
            for branch in branches:
                ident = len(rows) + 1
                candidate = branch["candidates"][0]
                event = next(e for e in arc["events"] if e["id"] == branch["event"])
                try:
                    from tools.v03_inline_delivery_adapter import _kor_source_binding
                except ModuleNotFoundError:
                    from v03_inline_delivery_adapter import _kor_source_binding
                source_binding = _kor_source_binding(journal["id"], journal["script"], candidate_parser=_queue_candidates, exclusion_parser=lambda _s: [])
                source_node_row = source_binding["branches"][branch["branch_index"]]
                native_branch = parse_block("{ " + journal["script"][source_node_row["start"]:source_node_row["end"]] + " }")[0]
                refs = set(_node_refs((native_branch,)))
                refs.update(native_queues)
                for stem in native_stems:
                    refs.update(stem + suffix for suffix in ("_36_notice", "_notice_delivery_active", "_notice_delivery_12", "_notice_delivery_36", "_12_notice_delivered", "_36_notice_delivered"))
                rows.append({"id": ident, "arc": arc, "journal": journal, "branch": branch,
                             "candidate": candidate, "event": event,
                             "snapshot_refs": sorted(refs), "native_branch": native_branch})
                updates.append((branch, ident, candidate))
            # Insert by original offsets from end to start so every branch and
            # every native pre/post AST remains byte-source bound.
            for branch, ident, candidate in reversed(updates):
                original = script[branch["start"]:branch["end"]]
                row = rows[ident - 1]
                root = parse_block("{ " + original + " }")[0]
                fields = list(children(root))
                limits = [n for n in fields if n.key == "limit"]
                events = [n for n in fields if n.key == "trigger_event"]
                if len(limits) != 1 or len(events) != 1:
                    raise ValueError(f"{journal['id']}: unsupported sender layout")
                wrapped = "{ " + original + " }"
                limit_inner = render_node(limits[0], wrapped)
                lim_body = limit_inner[limit_inner.find("{") + 1:limit_inner.rfind("}")].strip()
                branch_kind = root.key
                output = [f"{branch_kind} = {{ limit = {{ AND = {{ {lim_body} {PREFIX}_turn_{ident} = yes }} }}",
                          f"    {PREFIX}_reserve_{ident} = yes"]
                trigger_index = next(i for i, n in enumerate(fields) if n.key == "trigger_event")
                removed = False
                for index, node in enumerate(fields):
                    if node.key == "limit":
                        continue
                    if index == trigger_index:
                        captures = []
                        for name in row["snapshot_refs"]:
                            safe = re.sub(r"[^a-z0-9_]", "_", name.removeprefix("ywc_jhg_"))
                            p = f"{PREFIX}_snapshot_{ident}_{safe}_present"
                            v = f"{PREFIX}_snapshot_{ident}_{safe}_value"
                            captures.extend((f"remove_variable = {p}", f"remove_variable = {v}",
                                f"set_variable = {{ name = {p} value = 0 }}", f"set_variable = {{ name = {v} value = 0 }}",
                                f"if = {{ limit = {{ has_variable = {name} }} set_variable = {{ name = {p} value = 1 }} set_variable = {{ name = {v} value = var:{name} }} }}"))
                        output.extend("    " + command for command in captures)
                        output.extend((f"    save_scope_value_as = {{ name = {PREFIX}_dispatch_candidate value = var:{PREFIX}_reservation }}",
                                       f"    save_scope_value_as = {{ name = {PREFIX}_dispatch_epoch value = var:{PREFIX}_reservation_epoch }}"))
                    if node.key == "remove_variable" and node.value == candidate["queue"] and not removed:
                        removed = True
                        continue
                    output.append("    " + render_node(node, wrapped))
                output.append(
                    f"    if = {{ limit = {{ {PREFIX}_source_boundary_owner_{ident} = yes }} "
                    f"set_variable = {{ name = {PREFIX}_source_boundary_{ident} value = {ident} }} "
                    f"set_variable = {{ name = {PREFIX}_source_boundary_epoch_{ident} value = var:{PREFIX}_reservation_epoch }} }}"
                )
                output.append(f"    {PREFIX}_sender_return_{ident} = yes")
                if not removed:
                    raise ValueError(f"{journal['id']}: selected queue removal was not found")
                output.append("}")
                replacement = " ".join(output)
                script = script[:branch["start"]] + replacement + script[branch["end"]:]
            pattern = re.compile(r"(on_monthly_pulse\s*=\s*\{\s*effect\s*=\s*\{)")
            script, count = pattern.subn(lambda match: match.group(1) + f" {PREFIX}_prepare = yes", script, count=1)
            if count != 1:
                raise ValueError(f"{journal['id']}: cannot place JHG scheduler preparation before monthly source work")
            journal_scripts[journal["id"]] = script

    candidate_count = len(rows)
    effects: list[str] = []
    triggers: list[str] = []
    event_hooks: dict[str, list[str]] = {}
    inline_proofs: dict[str, list[str]] = {}
    ack_hooks: dict[str, list[str]] = {}
    for row in rows:
        ident = row["id"]
        event_hooks.setdefault(row["event"]["id"], []).append(f"{PREFIX}_dispatch_{ident}")
        inline_proofs.setdefault(row["event"]["id"], []).append(f"{PREFIX}_body_return_{ident} = yes")
        ack_hooks.setdefault(row["event"]["id"], []).append(f"{PREFIX}_callback_{ident}")
    # A source dispatch can open only a live phase and exact native source
    # branch. The original priority chain remains the arbiter between branches.
    round_var = PREFIX + "_round"
    reservation = PREFIX + "_reservation"
    epoch_counter = PREFIX + "_epoch"
    epoch = PREFIX + "_reservation_epoch"
    timer = PREFIX + "_timer"
    served_vars = {arc["slug"]: f"{PREFIX}_served_{i + 1}" for i, arc in enumerate(arcs)}
    for row in rows:
        i = row["id"]
        arc, journal, branch, candidate = row["arc"], row["journal"], row["branch"], row["candidate"]
        q = candidate["queue"]
        proof = next(p for p in arc["inline_delivery_adapter"]["branches"] if p["journal"] == journal["id"] and p["branch_index"] == branch["branch_index"])
        witness = live[journal["id"]]
        event = row["event"]
        # Native variables directly read or written at the site are presence
        # and value captured at reservation and refreshed at source return.
        refs = row["snapshot_refs"]
        native_branch = row["native_branch"]
        def snap(name: str, suffix: str) -> str:
            safe = re.sub(r"[^a-z0-9_]", "_", name.removeprefix("ywc_jhg_"))
            return f"{PREFIX}_snapshot_{i}_{safe}_{suffix}"
        def r_snap(name: str, suffix: str) -> str:
            safe = re.sub(r"[^a-z0-9_]", "_", name.removeprefix("ywc_jhg_"))
            return f"{PREFIX}_r_snapshot_{i}_{safe}_{suffix}"
        def snapshot_check(name: str, name_fn: Any) -> str:
            p, v = name_fn(name, "present"), name_fn(name, "value")
            return ("OR = { "
                f"AND = {{ has_variable = {p} has_variable = {v} var:{p} = 1 has_variable = {name} var:{name} = var:{v} }} "
                f"AND = {{ has_variable = {p} has_variable = {v} var:{p} = 0 var:{v} = 0 NOT = {{ has_variable = {name} }} }} }}")
        def snapshot_checks() -> str:
            return " ".join(snapshot_check(name, snap) for name in refs)
        def r_snapshot_checks() -> str:
            return " ".join(snapshot_check(name, r_snap) for name in refs)

        # Derive R(P) from the exact native postfragment. P remains immutable;
        # the only current postfragment writes are the authored presence-based
        # delivered-marker choice on the six notice callsites.
        native_fields = list(children(native_branch))
        trigger_index = next(index for index, node in enumerate(native_fields)
                             if node.key == "trigger_event")
        post_nodes = native_fields[trigger_index + 1:]
        post_choice: tuple[str, str, str, str, str] | None = None
        if post_nodes:
            if (len(post_nodes) != 2 or post_nodes[0].key != "if"
                    or post_nodes[1].key != "else"):
                raise ValueError(f"JHG source postfragment has unsupported shape at candidate {i}")
            limits = direct_values(children(post_nodes[0]), "limit")
            true_writes = direct_values(children(post_nodes[0]), "set_variable")
            false_writes = direct_values(children(post_nodes[1]), "set_variable")
            if len(limits) != 1 or len(true_writes) != 1 or len(false_writes) != 1:
                raise ValueError(f"JHG source postfragment assignment inventory changed at candidate {i}")
            discriminators = direct_values(children(limits[0]), "has_variable")
            if len(discriminators) != 1 or not isinstance(discriminators[0].value, str):
                raise ValueError(f"JHG source postfragment discriminator changed at candidate {i}")
            def assignment(node: Any) -> tuple[str, str]:
                names = direct_values(children(node), "name")
                values = direct_values(children(node), "value")
                if len(names) != 1 or len(values) != 1:
                    raise ValueError(f"JHG source postfragment assignment changed at candidate {i}")
                return str(names[0].value), str(values[0].value)
            true_name, true_value = assignment(true_writes[0])
            false_name, false_value = assignment(false_writes[0])
            post_choice = (str(discriminators[0].value), true_name, true_value,
                           false_name, false_value)
        written_names = set() if post_choice is None else {post_choice[1], post_choice[3]}
        source_r_checks = [snapshot_check(name, snap) for name in refs
                           if name not in written_names]
        if post_choice is not None:
            discriminator, true_name, true_value, false_name, false_value = post_choice
            p = snap(discriminator, "present")
            def assigned(name: str, value: str) -> str:
                return f"has_variable = {name} var:{name} = {value}"
            true_case = (f"has_variable = {p} var:{p} = 1 {assigned(true_name, true_value)} "
                         f"{snapshot_check(false_name, snap)}")
            false_case = (f"has_variable = {p} var:{p} = 0 {assigned(false_name, false_value)} "
                          f"{snapshot_check(true_name, snap)}")
            source_r_checks.append(f"OR = {{ AND = {{ {true_case} }} AND = {{ {false_case} }} }}")
        source_r_guard = " ".join(source_r_checks)
        r_captures = []
        for name in refs:
            p, v = r_snap(name, "present"), r_snap(name, "value")
            r_captures.extend((f"remove_variable = {p}", f"remove_variable = {v}",
                f"set_variable = {{ name = {p} value = 0 }}", f"set_variable = {{ name = {v} value = 0 }}",
                f"if = {{ limit = {{ has_variable = {name} }} set_variable = {{ name = {p} value = 1 }} set_variable = {{ name = {v} value = var:{name} }} }}"))
        native_context = []
        limits = direct_values(children(native_branch), "limit")
        def context_atoms(nodes: Any) -> None:
            for atom in nodes:
                if atom.key in {"OR", "NOT", "NOR"}:
                    continue
                if atom.key == "AND" and isinstance(atom.value, tuple):
                    context_atoms(children(atom))
                elif atom.key.startswith("var:ywc_jhg_") and atom.key != "var:" + q and atom.op in {"=", ">", "<", ">=", "<=", "!="}:
                    native_context.append(f"{atom.key} {atom.op} {atom.value}")
                elif atom.key == "has_variable" and atom.value != q:
                    native_context.append(f"has_variable = {atom.value}")
        if limits:
            context_atoms(children(limits[0]))
        native_context = list(dict.fromkeys(native_context))
        token_guard = (f"exists = scope:{PREFIX}_dispatch_candidate scope:{PREFIX}_dispatch_candidate > 0 "
            f"scope:{PREFIX}_dispatch_candidate = {i} exists = scope:{PREFIX}_dispatch_epoch "
            f"scope:{PREFIX}_dispatch_epoch > 0 scope:{PREFIX}_dispatch_epoch = var:{epoch}")
        reservation_live = f"has_variable = {timer} var:{timer} = 1"
        base_guard = (f"has_journal_entry = {journal['id']} {reservation_live} var:{reservation} = {i} var:{epoch_counter} > 0 var:{epoch} > 0 var:{PREFIX}_candidate_epoch_{i} > 0 "
            f"var:{PREFIX}_candidate_epoch_{i} = var:{epoch} has_variable = {witness} var:{witness} = 1 "
            f"var:{q} = {candidate['value']} {token_guard} " + " ".join(native_context))
        # This is the validated R(P) capture. The P snapshots made at the
        # trigger boundary stay immutable for the rest of this reservation.
        captures = []
        for name in refs:
            p, v = snap(name, "present"), snap(name, "value")
            captures.extend((f"remove_variable = {p}", f"remove_variable = {v}",
                f"set_variable = {{ name = {p} value = 0 }}", f"set_variable = {{ name = {v} value = 0 }}",
                f"if = {{ limit = {{ has_variable = {name} }} set_variable = {{ name = {p} value = 1 }} set_variable = {{ name = {v} value = var:{name} }} }}"))
        reserve_effects = [f"remove_variable = {PREFIX}_source_boundary_{i}",
            f"remove_variable = {PREFIX}_source_boundary_epoch_{i}",
            f"remove_variable = {PREFIX}_sender_completed_{i}", f"remove_variable = {PREFIX}_sender_completed_epoch_{i}",
            f"remove_variable = {PREFIX}_body_completed_{i}", f"remove_variable = {PREFIX}_body_completed_epoch_{i}",
            f"remove_variable = {PREFIX}_callback_{i}", f"remove_variable = {PREFIX}_callback_candidate_{i}",
            f"remove_variable = {PREFIX}_callback_epoch_{i}", f"remove_variable = {PREFIX}_callback_queue_{i}"]
        reserve_effects.extend(f"remove_variable = {r_snap(name, suffix)}"
                               for name in refs for suffix in ("present", "value"))
        reserve_effects.extend(captures)
        reserve_effects += [f"if = {{ limit = {{ has_variable = {epoch_counter} var:{epoch_counter} > 0 }} change_variable = {{ name = {epoch_counter} add = 1 }} }}",
            f"if = {{ limit = {{ NOT = {{ has_variable = {epoch_counter} }} }} set_variable = {{ name = {epoch_counter} value = 1 }} }}",
            f"if = {{ limit = {{ has_variable = {epoch_counter} NOT = {{ var:{epoch_counter} > 0 }} }} set_variable = {{ name = {epoch_counter} value = 1 }} }}",
            f"set_variable = {{ name = {epoch} value = var:{epoch_counter} }}",
            f"set_variable = {{ name = {PREFIX}_candidate_epoch_{i} value = var:{epoch} }}",
            f"set_variable = {{ name = {reservation} value = {i} }}",
            f"set_variable = {{ name = {timer} value = 1 days = 90 }}"]
        effects.append(f"{PREFIX}_reserve_{i} = {{ if = {{ limit = {{ {PREFIX}_turn_{i} = yes {PREFIX}_candidate_{i} = yes NOT = {{ has_variable = {reservation} }} NOT = {{ has_variable = {timer} }} }} {' '.join(reserve_effects)} }} }}")
        phase_guard = f"AND = {{ has_variable = {witness} var:{witness} = 1 {PREFIX}_turn_{i} = yes {PREFIX}_candidate_{i} = yes }}"
        candidate_checks = [f"has_journal_entry = {journal['id']}", f"has_variable = {witness}", f"var:{witness} = 1", f"NOT = {{ has_variable = {reservation} }}", f"NOT = {{ has_variable = {timer} }}", f"NOT = {{ var:{served_vars[arc['slug']]} = var:{round_var} }}"]
        # Current authored native dispatch branch conditions are duplicated
        # as a real predicate and remain subordinate to the original chain.
        candidate_checks += [f"var:{q} = {candidate['value']}"]
        candidate_checks += native_context
        triggers.append(f"{PREFIX}_turn_{i} = {{ AND = {{ NOT = {{ has_variable = {reservation} }} NOT = {{ has_variable = {timer} }} {PREFIX}_candidate_{i} = yes }} }}")
        triggers.append(f"{PREFIX}_candidate_{i} = {{ {' '.join(candidate_checks)} }}")
        boundary_reached = (f"AND = {{ has_variable = {PREFIX}_source_boundary_{i} "
            f"var:{PREFIX}_source_boundary_{i} = {i} has_variable = {PREFIX}_source_boundary_epoch_{i} "
            f"var:{PREFIX}_source_boundary_epoch_{i} = var:{epoch} }}")
        source_boundary_owner_guard = (
            f"has_variable = {reservation} var:{reservation} = {i} "
            f"has_variable = {epoch_counter} var:{epoch_counter} > 0 "
            f"has_variable = {epoch} var:{epoch} > 0 var:{epoch} = var:{epoch_counter} "
            f"has_variable = {PREFIX}_candidate_epoch_{i} "
            f"var:{PREFIX}_candidate_epoch_{i} > 0 var:{PREFIX}_candidate_epoch_{i} = var:{epoch} "
            f"{token_guard}"
        )
        triggers.append(
            f"{PREFIX}_source_boundary_owner_{i} = {{ AND = {{ {source_boundary_owner_guard} }} }}"
        )
        boundary_absent = (f"NOT = {{ has_variable = {PREFIX}_source_boundary_{i} }} "
            f"NOT = {{ has_variable = {PREFIX}_source_boundary_epoch_{i} }}")
        dispatch_snapshot = (f"OR = {{ AND = {{ NOT = {{ has_variable = {PREFIX}_sender_completed_{i} }} "
            f"{boundary_absent} {snapshot_checks()} }} "
            f"AND = {{ has_variable = {PREFIX}_sender_completed_{i} var:{PREFIX}_sender_completed_{i} = 1 "
            f"var:{PREFIX}_sender_completed_epoch_{i} = var:{epoch} {boundary_reached} {r_snapshot_checks()} }} }}")
        dispatch_checks = [f"has_journal_entry = {journal['id']}", reservation_live, f"var:{reservation} = {i}", f"var:{epoch_counter} > 0", f"var:{epoch} > 0", f"var:{PREFIX}_candidate_epoch_{i} > 0", f"var:{PREFIX}_candidate_epoch_{i} = var:{epoch}",
            f"has_variable = {witness}", f"var:{witness} = 1", f"var:{q} = {candidate['value']}",
            f"NOT = {{ has_variable = {PREFIX}_body_completed_{i} }}",
            f"NOT = {{ has_variable = {PREFIX}_body_completed_epoch_{i} }}",
            token_guard, dispatch_snapshot]
        triggers.append(f"{PREFIX}_dispatch_{i} = {{ {' '.join(dispatch_checks)} }}")
        receipt_common = base_guard
        source_return_guard = receipt_common + " " + source_r_guard + " " + boundary_reached
        effects.append(f"{PREFIX}_sender_return_{i} = {{ if = {{ limit = {{ {source_return_guard} }} {' '.join(r_captures)} set_variable = {{ name = {PREFIX}_sender_completed_{i} value = 1 }} set_variable = {{ name = {PREFIX}_sender_completed_epoch_{i} value = var:{epoch} }} {PREFIX}_join_{i} = yes }} }}")
        effects.append(f"{PREFIX}_body_return_{i} = {{ if = {{ limit = {{ {receipt_common} }} set_variable = {{ name = {PREFIX}_body_completed_{i} value = 1 }} set_variable = {{ name = {PREFIX}_body_completed_epoch_{i} value = var:{epoch} }} {PREFIX}_join_{i} = yes }} }}")
        effects.append(f"{PREFIX}_callback_{i} = {{ if = {{ limit = {{ {receipt_common} }} set_variable = {{ name = {PREFIX}_callback_{i} value = 1 }} set_variable = {{ name = {PREFIX}_callback_candidate_{i} value = {i} }} set_variable = {{ name = {PREFIX}_callback_epoch_{i} value = var:{epoch} }} set_variable = {{ name = {PREFIX}_callback_queue_{i} value = var:{q} }} {PREFIX}_join_{i} = yes }} }}")
        complete = (f"{receipt_common} has_variable = {PREFIX}_sender_completed_{i} var:{PREFIX}_sender_completed_{i} = 1 "
            f"var:{PREFIX}_sender_completed_epoch_{i} = var:{epoch} has_variable = {PREFIX}_body_completed_{i} "
            f"var:{PREFIX}_body_completed_{i} = 1 var:{PREFIX}_body_completed_epoch_{i} = var:{epoch} "
            f"has_variable = {PREFIX}_callback_{i} var:{PREFIX}_callback_{i} = 1 var:{PREFIX}_callback_candidate_{i} = {i} "
            f"var:{PREFIX}_callback_epoch_{i} = var:{epoch} var:{PREFIX}_callback_queue_{i} = var:{q} {r_snapshot_checks()}")
        effects.append(f"{PREFIX}_join_{i} = {{ if = {{ limit = {{ {complete} }} {PREFIX}_ack_{i} = yes }} }}")
        effects.append(f"{PREFIX}_ack_{i} = {{ if = {{ limit = {{ {complete} }} remove_variable = {q} remove_variable = {timer} remove_variable = {reservation} remove_variable = {PREFIX}_source_boundary_{i} remove_variable = {PREFIX}_source_boundary_epoch_{i} set_variable = {{ name = {served_vars[arc['slug']]} value = var:{round_var} }} }} }}")

    # All three arcs participate in a round-robin service ledger. A round only
    # advances when every currently eligible arc has either been served or is
    # no longer eligible; the actual authored if/else chains keep priority.
    all_eligible = " OR = { " + " ".join(f"{PREFIX}_candidate_{r['id']} = yes" for r in rows) + " }"
    served_reset = " OR = { " + " ".join(f"AND = {{ {PREFIX}_candidate_{r['id']} = yes var:{served_vars[r['arc']['slug']]} != var:{round_var} }}" for r in rows) + " }"
    eligible_arc = {arc["slug"]: " OR = { " + " ".join(f"{PREFIX}_candidate_{r['id']} = yes" for r in rows if r["arc"]["slug"] == arc["slug"]) + " }" for arc in arcs}
    round_advance = " AND = { " + " ".join(f"OR = {{ NOT = {{ {eligible_arc[a['slug']]} }} var:{served_vars[a['slug']]} = var:{round_var} }}" for a in arcs) + " }"
    effects.append(f"{PREFIX}_prepare = {{ if = {{ limit = {{ NOT = {{ has_variable = {round_var} }} }} set_variable = {{ name = {round_var} value = 1 }} }} if = {{ limit = {{ has_variable = {reservation} NOT = {{ has_variable = {timer} }} }} remove_variable = {reservation} {' '.join(f'remove_variable = {n}' for r in rows for n in (f'{PREFIX}_sender_completed_{r["id"]}',f'{PREFIX}_sender_completed_epoch_{r["id"]}',f'{PREFIX}_body_completed_{r["id"]}',f'{PREFIX}_body_completed_epoch_{r["id"]}',f'{PREFIX}_callback_{r["id"]}',f'{PREFIX}_callback_candidate_{r["id"]}',f'{PREFIX}_callback_epoch_{r["id"]}',f'{PREFIX}_callback_queue_{r["id"]}'))} }} if = {{ limit = {{ has_variable = {reservation} NOT = {{ OR = {{ {' '.join(f'var:{reservation} = {r["id"]}' for r in rows)} }} }} NOT = {{ has_variable = {timer} }} }} remove_variable = {reservation} }} if = {{ limit = {{ NOT = {{ has_variable = {reservation} }} NOT = {{ has_variable = {timer} }} {round_advance} }} change_variable = {{ name = {round_var} add = 1 }} }} }}")
    triggers.append(f"{PREFIX}_round = {{ has_variable = {round_var} }}")

    return {"effects": "\n".join(effects) + "\n", "triggers": "\n".join(triggers) + "\n",
            "event_hooks": event_hooks, "inline_proofs": inline_proofs, "ack_hooks": ack_hooks,
            "journal_scripts": journal_scripts, "live_witnesses": live,
            "guarded_immediate_events": sorted(event_hooks)}


def render_jhg_inline_country_adapters(catalog: dict[str, Any]) -> dict[str, Any]:
    return _render_adapter(catalog)


def validate_jhg_inline_catalog(catalog: dict[str, Any]) -> None:
    _validate_catalog(catalog)
