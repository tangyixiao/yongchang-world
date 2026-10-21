"""Strict source-span parser and generated adapters for inline Clausewitz senders."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
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
            if node.key.startswith(("var:ywc_kor_", "var:ywc_nqg_")) and node.op == "=" and node.value.isdigit():
                raw = node.key.removeprefix("var:")
                if raw.endswith(("_pending_event", "_notice_event", "_pending")):
                    variable, mode, value = raw, "exact", int(node.value)
            elif node.key == "has_variable" and node.op == "=" and node.value.startswith(("ywc_kor_", "ywc_nqg_")):
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
            if node.key.startswith(("var:ywc_kor_", "var:ywc_nqg_")) and node.key.removeprefix("var:").endswith(("_pending_event", "_notice_event", "_pending")):
                exclusions.append({"queue": node.key.removeprefix("var:"), "op": node.op, "mode": "exact", "value": node.value})
            elif node.key == "has_variable" and node.value.startswith(("ywc_kor_", "ywc_nqg_")) and node.value.endswith(("_pending_event", "_notice_event", "_pending")):
                exclusions.append({"queue": node.value, "op": node.op, "mode": "presence"})
    visit(children(limits[0]))
    return exclusions


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

def validate_inline_catalog(catalog: dict[str, Any]) -> None:
    """Validate exact inline branch/source ownership for explicitly opted-in arcs."""
    if isinstance(catalog, dict) and catalog.get("key") == "country_kor":
        _validate_kor_inline_catalog(catalog)
        return
    if isinstance(catalog, dict) and catalog.get("key") == "country_nqg":
        _validate_nqg_inline_catalog(catalog)
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
            candidates = proof.get("candidates")
            if not isinstance(candidates, list) or len(candidates) != len(source["candidates"]):
                raise ValueError(f"{arc['slug']}/{jid}: queue candidate inventory drift")
            for candidate, expected_candidate in zip(candidates, source["candidates"]):
                allowed = {"queue", "kind", "mode"} | ({"value"} if expected_candidate["mode"] == "exact" else set())
                if not isinstance(candidate, dict) or set(candidate) != allowed or candidate != expected_candidate:
                    raise ValueError(f"{arc['slug']}/{jid}: queue semantics do not match positive source predicates")
                if "value" in candidate and type(candidate["value"]) is not int:
                    raise ValueError(f"{arc['slug']}/{jid}: queue value must be an integer")
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
            if len(direct_triggers) != 1 or source["event"] != late_events[arc["slug"]] and any(candidate["kind"] != "normal_queued_event" for candidate in expected_candidates):
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
                if not isinstance(candidate, dict) or set(candidate) != allowed or candidate.get("kind") not in {"normal_queued_event", "notice12", "notice36", "remedy_final"}:
                    raise ValueError(f"{arc['slug']}/{jid}: malformed candidate class")
                if any(type(candidate.get(field)) is not str for field in ("queue", "kind", "mode")):
                    raise ValueError(f"{arc['slug']}/{jid}: candidate fields must be strings")
                if "value" in candidate and type(candidate["value"]) is not int:
                    raise ValueError(f"{arc['slug']}/{jid}: exact queue value must be an integer")
                expected_suffix = {"normal_queued_event": "pending", "notice12": "notice12_pending", "notice36": "notice36_pending", "remedy_final": "remedy_final_pending"}[candidate["kind"]]
                if candidate["queue"] != f"ywc_nqg_{base}_{expected_suffix}":
                    raise ValueError(f"{arc['slug']}/{jid}: candidate queue is not owned by its arc and class")
                if candidate["kind"] == "normal_queued_event":
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
    queue_id = re.sub(r"[^a-z0-9_]", "_", queue.removeprefix("ywc_dmg_").removeprefix("ywc_kor_").removeprefix("ywc_nqg_"))
    return _script_var(f"{prefix}_c{candidate_id}_{queue_id}_{suffix}")


def _branch_node(pulse: str, branch: dict[str, Any]) -> tuple[Node, Node, Node]:
    top = parse_block(pulse)
    monthly = direct_values(top, "on_monthly_pulse")
    effect = direct_values(children(monthly[0]), "effect")
    sender_nodes = []
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


def render_inline_country_adapters(catalog: dict[str, Any]) -> dict[str, Any]:
    """Render source-bound per-branch dispatch gates, snapshots and immediate ACKs."""
    validate_inline_catalog(catalog)
    is_kor = catalog["key"] == "country_kor"
    is_nqg = catalog["key"] == "country_nqg"
    prefix = "ywc_v03_kor_inline" if is_kor else "ywc_v03_nqg_inline" if is_nqg else "ywc_v03_dmg_inline"
    arcs = [arc for arc in catalog["arcs"] if arc.get("era") == "foundation"]
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
            binding = _kor_source_binding(journal["id"], journal["script"]) if (is_kor or is_nqg) else source_binding(journal["id"], journal["script"])
            branch = binding["branches"][proof["branch_index"]]
            for queue in proof["candidates"]:
                event = next(e for e in arc["events"] if e["id"] == proof["event"])
                receipt_pattern = r"name\s*=\s*(ywc_v03_dmg_[a-z0-9_]*_last_event)\s+value\s*=\s*([0-9]+)"
                receipt_match = re.search(receipt_pattern, event["immediate"])
                if not receipt_match and not (is_kor or is_nqg): raise ValueError(f"{event['id']}: source immediate lacks a last_event receipt")
                receipt_variable = receipt_match.group(1) if receipt_match else None
                intent_variable = open_variable = None
                if is_nqg and queue["kind"] in {"notice12", "notice36"}:
                    suffix = "12" if queue["kind"] == "notice12" else "36"
                    stem = queue["queue"].removesuffix(f"notice{suffix}_pending")
                    intent_variable = stem + f"notice{suffix}_intent"
                    open_variable = stem + f"notice{suffix}_open"
                    receipt_variable = stem + f"blocked_{suffix}_delivered"
                rank_map = ({"normal": 0, "notice": 1} if is_kor else {"normal": 0, "notice36": 1, "notice12": 2} if not is_nqg else {"normal_queued_event": 0, "notice36": 1, "notice12": 2, "remedy_final": 3})
                candidates.append({"id": len(candidates) + 1, "key": f"c{len(candidates)+1}", "arc": arc, "journal": journal, "phase": phases[journal["id"]]["phase"], "branch": branch, "proof": proof, "queue": queue, "event": event, "receipt_variable": receipt_variable, "receipt_value": int(receipt_match.group(2)) if receipt_match else None, "intent_variable": intent_variable, "open_variable": open_variable, "rank": rank_map[queue["kind"]]})
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
        lim = _inner_text(c["branch"]["limit_source"][c["branch"]["limit_source"].find("{"):])
        event_guard = _inner_text(c["event"]["trigger"])
        goal = _inner_text(c["journal"]["goal"])
        fail = _inner_text(c["journal"]["exit_conditions"])
        q = c["queue"]
        queue_gate = f"has_variable = {q['queue']}" if q["mode"] == "presence" else f"var:{q['queue']} = {q['value']}"
        source_class = "AND = { " + lim + " " + queue_gate + " }"
        parts = [f"has_journal_entry = {c['journal']['id']}", f"has_variable = {c['phase']['live_witness']}", source_class, event_guard]
        if is_kor or is_nqg:
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
        lim = _inner_text(c["branch"]["limit_source"][c["branch"]["limit_source"].find("{"):])
        event_guard = _inner_text(c["event"]["trigger"])
        goal = _inner_text(c["journal"]["goal"])
        fail = _inner_text(c["journal"]["exit_conditions"])
        queue_gate = f"has_variable = {q['queue']}" if q["mode"] == "presence" else f"var:{q['queue']} = {q['value']}"
        source_class = "AND = { " + lim + " " + queue_gate + " }"
        for other in candidates:
            if other["id"] == c["id"]: continue
            higher = other["rank"] > c["rank"]
            earlier_tie = other["rank"] == c["rank"] and (arc_order[other["arc"]["slug"]] < arc_order[slug] or (other["arc"]["slug"] == slug and other["id"] < c["id"]))
            if higher or earlier_tie:
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
        if is_nqg:
            dispatch_checks += [f"has_journal_entry = {c['journal']['id']}", f"has_variable = {c['phase']['live_witness']}", source_class, event_guard]
            if goal: dispatch_checks.append(f"NOT = {{ {goal} }}")
            if fail: dispatch_checks.append(f"NOT = {{ {fail} }}")
            for prior in c["proof"].get("chain_prior", []):
                dispatch_checks.append("NOT = { " + _limit_inner_source(prior["limit_source"]) + " }")
            dispatch_checks.append(f"NOT = {{ var:{served[slug]} = var:{roundv} }}")
            dispatch_checks.extend(eligibility_terms[2:])
        else:
            dispatch_checks += eligibility_terms
        if is_kor or is_nqg:
            dispatch_checks.append(f"var:{prefix}_candidate_epoch_{c['id']} = var:{epoch}")
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
        }) if not is_kor else []
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
        triggers.append(f"{dispatch(c)} = {{ AND = {{ {' '.join(dispatch_checks)} }} }}")
    # Per-JE live witness and source lifecycle are handled by the journal renderer.
    any_candidates = " OR = { " + " ".join(f"{cid(c)} = yes" for c in candidates) + " }"
    reset_checks=[]
    for arc in arcs:
        slug=arc["slug"]; own=[c for c in candidates if c["arc"]["slug"]==slug]
        reset_checks.append("OR = { NOT = { OR = { "+" ".join(f"{cid(c)} = yes" for c in own)+" } } var:"+served[slug]+" = var:"+roundv+" }")
    kor_ephemeral: list[str] = []
    ephemeral_by_candidate: dict[int, list[str]] = {}
    if is_kor or is_nqg:
        for c in candidates:
            ident=c["id"]; qvar=c["queue"]["queue"]
            names=[f"{prefix}_callback_{ident}", f"{prefix}_callback_candidate_{ident}",
                   f"{prefix}_callback_epoch_{ident}", f"{prefix}_callback_queue_{ident}",
                   f"{prefix}_candidate_epoch_{ident}", _queue_snapshot_name(ident,qvar,"present",prefix),
                   _queue_snapshot_name(ident,qvar,"value",prefix)]
            if is_nqg:
                names.extend(_queue_snapshot_name(ident, state, suffix, prefix)
                             for state in _nqg_candidate_state(c, candidates) for suffix in ("present", "value"))
            ephemeral_by_candidate[ident] = names
            kor_ephemeral.extend(names)
    kor_cleanup = " ".join(f"remove_variable = {name}" for name in kor_ephemeral)
    prep=[f"{prefix}_prepare = {{",f"    if = {{ limit = {{ NOT = {{ has_variable = {roundv} }} }} set_variable = {{ name = {roundv} value = 1 }} }}"]
    if is_nqg:
        for c in candidates:
            ident=c["id"]; intent=c.get("intent_variable")
            baseguard=[f"var:{reservation} = {ident}", f"var:{prefix}_candidate_epoch_{ident} = var:{epoch}"]
            rollback=""
            if intent:
                pvar=_queue_snapshot_name(ident,intent,"present",prefix)
                vvar=_queue_snapshot_name(ident,intent,"value",prefix)
                rollback=(f" if = {{ limit = {{ has_variable = {pvar} has_variable = {vvar} has_variable = {intent} var:{intent} = 1 }} set_variable = {{ name = {intent} value = var:{vvar} }} }}"
                          f" if = {{ limit = {{ NOT = {{ has_variable = {pvar} }} has_variable = {intent} var:{intent} = 1 }} remove_variable = {intent} }}")
            clear=" ".join(f"remove_variable = {name}" for name in ephemeral_by_candidate[ident])
            stale_cond=f"AND = {{ {' '.join(baseguard)} {cid(c)} = no }}"
            prep.append(f"    if = {{ limit = {{ {stale_cond} }}{rollback} remove_variable = {reservation} remove_variable = {timer} {clear} }}")
            expired_cond=f"AND = {{ {' '.join(baseguard)} NOT = {{ has_variable = {timer} }} }}"
            prep.append(f"    if = {{ limit = {{ {expired_cond} }}{rollback} remove_variable = {reservation} {clear} }}")
    else:
        prep.append(f"    if = {{ limit = {{ var:{reservation} > 0 NOT = {{ has_variable = {timer} }} }} remove_variable = {reservation}{(' ' + kor_cleanup) if kor_cleanup else ''} }}")
    stale=" OR = { "+" ".join(f"AND = {{ var:{reservation} = {c['id']} NOT = {{ {cid(c)} = yes }} }}" for c in candidates)+" }"
    if not is_nqg:
        prep.append(f"    if = {{ limit = {{ has_variable = {timer} {stale} }} remove_variable = {reservation} remove_variable = {timer}{(' ' + kor_cleanup) if kor_cleanup else ''} }}")
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
        notice_queues=sorted({x["queue"]["queue"] for x in candidates if x["arc"]["slug"]==c["arc"]["slug"] and x["queue"]["kind"].startswith("notice")})
        capture=[f"if = {{ limit = {{ {turn(c)} = yes {cid(c)} = yes NOT = {{ has_variable = {reservation} }} }}"]
        if is_kor or is_nqg:
            capture += [f"    if = {{ limit = {{ has_variable = {epoch} }} change_variable = {{ name = {epoch} add = 1 }} }}", f"    if = {{ limit = {{ NOT = {{ has_variable = {epoch} }} }} set_variable = {{ name = {epoch} value = 1 }} }}"]
            capture += [f"    remove_variable = {name}" for name in (ephemeral_by_candidate[ident] if is_nqg else kor_ephemeral)]
            capture += [f"    set_variable = {{ name = {prefix}_candidate_epoch_{ident} value = var:{epoch} }}"]
        capture += [f"    set_variable = {{ name = {reservation} value = {ident} }}",f"    set_variable = {{ name = {snap_present} value = 1 }}",f"    set_variable = {{ name = {snap_value} value = var:{qvar} }}",f"    set_variable = {{ name = {timer} value = 1 days = 1 }}"]
        if is_nqg:
            for name in _nqg_candidate_state(c, candidates):
                pvar=_queue_snapshot_name(ident,name,"present",prefix); vvar=_queue_snapshot_name(ident,name,"value",prefix)
                capture += [f"    remove_variable = {pvar}", f"    remove_variable = {vvar}", f"    if = {{ limit = {{ has_variable = {name} }} set_variable = {{ name = {pvar} value = 1 }} set_variable = {{ name = {vvar} value = var:{name} }} }}"]
        else:
            for notice in notice_queues:
                for name in (notice, notice.replace("_notice", "_delivered")):
                    if name==qvar and name.endswith("_notice"): continue
                    pvar=_queue_snapshot_name(ident,name,"present",prefix); vvar=_queue_snapshot_name(ident,name,"value",prefix)
                    capture += [f"    remove_variable = {pvar}", f"    remove_variable = {vvar}", f"    if = {{ limit = {{ has_variable = {name} }} set_variable = {{ name = {pvar} value = 1 }} set_variable = {{ name = {vvar} value = var:{name} }} }}"]
        capture.append("}")
        effects.append(f"{prefix}_reserve_{ident} = {{ {' '.join(capture)} }}")
        # ACK is callable only from this event's actual immediate hook and must match receipt + reservation.
        ack=f"{prefix}_ack_{ident}"
        if is_kor or is_nqg:
            checks=[f"var:{reservation} = {ident}",f"has_variable = {timer}",f"has_variable = {snap_present}",f"has_variable = {snap_value}",f"has_journal_entry = {c['journal']['id']}",f"has_variable = {c['phase']['live_witness']}"]
            checks += [f"has_variable = {callback_proof}", f"var:{callback_id} = {ident}", f"var:{callback_epoch} = var:{epoch}", f"var:{prefix}_candidate_epoch_{ident} = var:{epoch}", f"var:{callback_queue} = var:{snap_value}", f"has_variable = {q['queue']}", f"var:{q['queue']} = var:{snap_value}", f"NOT = {{ var:{served[c['arc']['slug']]} = var:{roundv} }}"]
        else:
            checks=[f"var:{reservation} = {ident}",f"has_variable = {timer}",f"has_variable = {snap_present}",f"has_variable = {snap_value}",f"has_variable = {c['receipt_variable']}",f"var:{c['receipt_variable']} = {c['receipt_value']}",f"has_journal_entry = {c['journal']['id']}",f"has_variable = {c['phase']['live_witness']}"]
        goal=_inner_text(c["journal"]["goal"]); fail=_inner_text(c["journal"]["exit_conditions"])
        if goal: checks.append(f"NOT = {{ {goal} }}")
        if fail: checks.append(f"NOT = {{ {fail} }}")
        if q["mode"]=="exact": checks.append(f"var:{snap_value} = {q['value']}")
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
        if is_kor or is_nqg: body_parts += [f"remove_variable = {callback_proof}",f"remove_variable = {callback_id}",f"remove_variable = {callback_epoch}",f"remove_variable = {callback_queue}",f"remove_variable = {prefix}_candidate_epoch_{ident}"]
        if is_nqg: body_parts += [f"remove_variable = {name}" for name in ephemeral_by_candidate[ident]]
        body=" ".join(body_parts)
        effects.append(f"{prefix}_ack_{ident} = {{ if = {{ limit = {{ {' '.join(checks)} }} {body} }} }}")
        if is_kor or is_nqg:
            callback_guard = [f"var:{reservation} = {ident}", f"has_variable = {timer}", f"has_variable = {snap_present}", f"has_variable = {snap_value}", f"has_variable = {qvar}", f"var:{qvar} = var:{snap_value}", f"has_journal_entry = {c['journal']['id']}", f"has_variable = {c['phase']['live_witness']}"]
            if q["mode"] == "exact": callback_guard.append(f"var:{snap_value} = {q['value']}")
            if goal: callback_guard.append(f"NOT = {{ {goal} }}")
            if fail: callback_guard.append(f"NOT = {{ {fail} }}")
            callback_guard.append(f"NOT = {{ var:{served[c['arc']['slug']]} = var:{roundv} }}")
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
            effects.append(f"{prefix}_callback_{ident} = {{ if = {{ limit = {{ {' '.join(callback_guard)} }} set_variable = {{ name = {callback_proof} value = 1 }} set_variable = {{ name = {callback_id} value = {ident} }} set_variable = {{ name = {callback_epoch} value = var:{epoch} }} set_variable = {{ name = {callback_queue} value = var:{qvar} }} {prefix}_ack_{ident} = yes }} }}")
    journal_scripts={}
    # Splice only proven sender limits and insert candidate-owned reservations before native source ops.
    for journal_id, journal_info in phases.items():
        journal=journal_info["journal"]; script=journal["script"]; binding=source_binding(journal_id,script)
        edits=[]
        for branch_index, group in branches_by_journal.get(journal_id,{}).items():
            branch=binding["branches"][branch_index]
            node,limit,trigger=_branch_node(script,branch)
            turns=" OR = { "+" ".join(f"{turn(c)} = yes" for c in group)+" }"
            reserve_calls=" ".join(f"if = {{ limit = {{ {turn(c)} = yes }} {prefix}_reserve_{c['id']} = yes }}" for c in group)
            if is_kor:
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
        script=script[:pulse.value_start+1]+f" {prefix}_prepare = yes "+script[pulse.value_start+1:]
        if is_kor:
            script = re.sub(r"[ \t]+(?=\r?\n)", "", script)
        journal_scripts[journal_id]=script
    event_hooks={}; ack_hooks={}
    for event_id, group in candidates_by_event.items():
        event_hooks[event_id]=[dispatch(c) for c in group]
        hooks=[]
        for c in group:
            hooks.append(f"{prefix}_callback_{c['id']}" if (is_kor or is_nqg) else f"ywc_v03_dmg_inline_ack_{c['id']}")
        ack_hooks[event_id]=hooks
    return {"triggers":"\n\n".join(triggers)+"\n","effects":"\n\n".join(effects)+"\n","event_hooks":event_hooks,"ack_hooks":ack_hooks,"guarded_immediate_events":sorted(event_hooks),"journal_scripts":journal_scripts,"live_witnesses":{j:p["phase"]["live_witness"] for j,p in phases.items()}}
