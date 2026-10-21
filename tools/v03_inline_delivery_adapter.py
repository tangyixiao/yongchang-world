"""Strict source-span parser and generated adapters for inline Clausewitz senders."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
from typing import Any

_TOKEN = re.compile(r'[A-Za-z_][A-Za-z0-9_:.]*|-?[0-9]+|\?=|>=|<=|!=|=|\{|\}|"(?:\\.|[^"\\])*"')


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
            if tokens[idx][0] in ("{", "}", "=", "?=", ">=", "<=", "!="):
                raise ValueError(f"unexpected structural token {tokens[idx][0]!r}")
            key, start, _ = tokens[idx]; idx += 1
            if idx >= len(tokens) or tokens[idx][0] not in ("=", "?=", ">=", "<=", "!="):
                raise ValueError(f"expected an operator after {key}")
            op = tokens[idx][0]
            idx += 1
            if idx >= len(tokens) or tokens[idx][0] in ("}", "=", "?=", ">=", "<=", "!="): raise ValueError(f"missing or invalid value for {key}")
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
        if node.key == "has_variable" and node.value.startswith("ywc_dmg_"):
            if node.value.endswith("_notice") or node.value.endswith("_emergency_notice"):
                variable, mode = node.value, "presence"
        elif node.key.startswith("var:ywc_dmg_") and node.op == "=" and node.value.isdigit():
            variable, mode, value = node.key.removeprefix("var:"), "exact", int(node.value)
        if not variable: continue
        if variable.endswith("_blocked_12_notice") or variable.endswith("_emergency_notice") or variable.endswith("_state_lost_notice"):
            kind = "notice12"
        elif variable.endswith("_blocked_36_notice"):
            kind = "notice36"
        elif variable.endswith("_pending_event"):
            kind = "normal"
        else:
            continue
        identity = (variable, kind)
        item = {"queue": variable, "mode": mode, "kind": kind}
        if mode == "exact": item["value"] = value
        found[identity] = item
    return sorted(found.values(), key=lambda item: (item["kind"], item["queue"], item.get("value", -1)))

def validate_inline_catalog(catalog: dict[str, Any]) -> None:
    """Validate exact inline branch/source ownership for explicitly opted-in arcs."""
    if not isinstance(catalog, dict) or catalog.get("key") != "country_dmg": raise ValueError("inline adapter is currently enabled only for country_dmg")
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

def _inner_text(block: str) -> str:
    value = block.strip()
    if len(value) < 2 or value[0] != "{" or value[-1] != "}": raise ValueError("expected a braced source block")
    parse_block(value)
    return value[1:-1].strip()


def _script_var(name: str) -> str:
    if not re.fullmatch(r"[a-z][a-z0-9_]*", name): raise ValueError(f"unsafe generated variable: {name}")
    return name


def _queue_snapshot_name(candidate_id: int, queue: str, suffix: str) -> str:
    return _script_var(f"ywc_v03_dmg_inline_c{candidate_id}_{queue.removeprefix('ywc_dmg_')}_{suffix}")


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


def render_inline_country_adapters(catalog: dict[str, Any]) -> dict[str, Any]:
    """Render source-bound per-branch dispatch gates, snapshots and immediate ACKs."""
    validate_inline_catalog(catalog)
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
            binding = source_binding(journal["id"], journal["script"])
            branch = binding["branches"][proof["branch_index"]]
            for queue in proof["candidates"]:
                event = next(e for e in arc["events"] if e["id"] == proof["event"])
                receipt_match = re.search(r"name\s*=\s*(ywc_v03_dmg_[a-z0-9_]*_last_event)\s+value\s*=\s*([0-9]+)", event["immediate"])
                if not receipt_match: raise ValueError(f"{event['id']}: source immediate lacks a last_event receipt")
                candidates.append({"id": len(candidates) + 1, "key": f"c{len(candidates)+1}", "arc": arc, "journal": journal, "phase": phases[journal["id"]]["phase"], "branch": branch, "proof": proof, "queue": queue, "event": event, "receipt_variable": receipt_match.group(1), "receipt_value": int(receipt_match.group(2)), "rank": {"normal": 0, "notice36": 1, "notice12": 2}[queue["kind"]]})
    cid = lambda c: f"ywc_v03_dmg_inline_candidate_{c['id']}"
    turn = lambda c: f"ywc_v03_dmg_inline_turn_{c['id']}"
    dispatch = lambda c: f"ywc_v03_dmg_inline_dispatch_{c['id']}"
    roundv = "ywc_v03_dmg_inline_round"
    reservation = "ywc_v03_dmg_inline_reservation"
    timer = "ywc_v03_dmg_inline_timer"
    served = {arc["slug"]: f"ywc_v03_dmg_inline_served_{arc_order[arc['slug']]+1}" for arc in arcs}
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
        if goal: parts.append(f"NOT = {{ {goal} }}")
        if fail: parts.append(f"NOT = {{ {fail} }}")
        triggers.append(f"{cid(c)} = {{ AND = {{ {' '.join(parts)} }} }}")
    # Per-candidate turn gate: dynamically compare only candidates that are live now.
    for c in candidates:
        slug = c["arc"]["slug"]; q = c["queue"]; blockers=[]
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
        snapshot_present = _queue_snapshot_name(c["id"], q["queue"], "present")
        snapshot_value = _queue_snapshot_name(c["id"], q["queue"], "value")
        # Dispatch is revalidated at the native event trigger, before its immediate
        # can clear notice flags. This proves the same exact source queue and phase
        # still own the reservation; the ACK then uses the captured queue snapshot
        # because native DMG notice helpers intentionally clear both notice classes.
        dispatch_checks = [f"var:{reservation} = {c['id']}", f"has_variable = {timer}",
                           f"has_variable = {snapshot_present}", f"has_variable = {snapshot_value}",
                           f"has_variable = {q['queue']}", f"var:{q['queue']} = var:{snapshot_value}",
                           *eligibility_terms]
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
        })
        tracked = set()
        for notice in notice_queues:
            tracked.add(notice)
            if notice.endswith("_blocked_12_notice") or notice.endswith("_blocked_36_notice"):
                tracked.add(notice.replace("_notice", "_delivered"))
        for name in sorted(tracked):
            present = _queue_snapshot_name(c["id"], name, "present")
            value = _queue_snapshot_name(c["id"], name, "value")
            dispatch_checks.append(
                "OR = { "
                f"AND = {{ has_variable = {present} has_variable = {value} "
                f"has_variable = {name} var:{name} = var:{value} }} "
                f"AND = {{ NOT = {{ has_variable = {present} }} "
                f"NOT = {{ has_variable = {value} }} NOT = {{ has_variable = {name} }} }} "
                "}"
            )
        if q["mode"] == "exact":
            dispatch_checks.append(f"var:{snapshot_value} = {q['value']}")
        triggers.append(f"{dispatch(c)} = {{ AND = {{ {' '.join(dispatch_checks)} }} }}")
    # Per-JE live witness and source lifecycle are handled by the journal renderer.
    any_candidates = " OR = { " + " ".join(f"{cid(c)} = yes" for c in candidates) + " }"
    reset_checks=[]
    for arc in arcs:
        slug=arc["slug"]; own=[c for c in candidates if c["arc"]["slug"]==slug]
        reset_checks.append("OR = { NOT = { OR = { "+" ".join(f"{cid(c)} = yes" for c in own)+" } } var:"+served[slug]+" = var:"+roundv+" }")
    prep=[f"ywc_v03_dmg_inline_prepare = {{",f"    if = {{ limit = {{ NOT = {{ has_variable = {roundv} }} }} set_variable = {{ name = {roundv} value = 1 }} }}"]
    prep.append(f"    if = {{ limit = {{ var:{reservation} > 0 NOT = {{ has_variable = {timer} }} }} remove_variable = {reservation} }}")
    stale=" OR = { "+" ".join(f"AND = {{ var:{reservation} = {c['id']} NOT = {{ {cid(c)} = yes }} }}" for c in candidates)+" }"
    prep.append(f"    if = {{ limit = {{ has_variable = {timer} {stale} }} remove_variable = {reservation} remove_variable = {timer} }}")
    prep.append(f"    if = {{ limit = {{ {any_candidates} AND = {{ {' '.join(reset_checks)} }} }} change_variable = {{ name = {roundv} add = 1 }} }}")
    prep.append("}"); effects.extend(prep)
    # Reservation captures exact source values before any native pre-trigger removal/helper.
    for c in candidates:
        q=c["queue"]; qvar=q["queue"]; ident=c["id"]
        snap_present=_queue_snapshot_name(ident,qvar,"present"); snap_value=_queue_snapshot_name(ident,qvar,"value")
        notice_queues=sorted({x["queue"]["queue"] for x in candidates if x["arc"]["slug"]==c["arc"]["slug"] and x["queue"]["kind"].startswith("notice")})
        capture=[f"if = {{ limit = {{ {turn(c)} = yes {cid(c)} = yes NOT = {{ has_variable = {reservation} }} }}",f"    set_variable = {{ name = {reservation} value = {ident} }}",f"    set_variable = {{ name = {snap_present} value = 1 }}",f"    set_variable = {{ name = {snap_value} value = var:{qvar} }}",f"    set_variable = {{ name = {timer} value = 1 days = 1 }}"]
        for notice in notice_queues:
            for name in (notice, notice.replace("_notice", "_delivered")):
                if name==qvar and name.endswith("_notice"): continue
                pvar=_queue_snapshot_name(ident,name,"present"); vvar=_queue_snapshot_name(ident,name,"value")
                capture += [f"    remove_variable = {pvar}", f"    remove_variable = {vvar}", f"    if = {{ limit = {{ has_variable = {name} }} set_variable = {{ name = {pvar} value = 1 }} set_variable = {{ name = {vvar} value = var:{name} }} }}"]
        capture.append("}")
        effects.append(f"ywc_v03_dmg_inline_reserve_{ident} = {{ {' '.join(capture)} }}")
        # ACK is callable only from this event's actual immediate hook and must match receipt + reservation.
        ack=f"ywc_v03_dmg_inline_ack_{ident}"
        checks=[f"var:{reservation} = {ident}",f"has_variable = {timer}",f"has_variable = {snap_present}",f"has_variable = {snap_value}",f"has_variable = {c['receipt_variable']}",f"var:{c['receipt_variable']} = {c['receipt_value']}",f"has_journal_entry = {c['journal']['id']}",f"has_variable = {c['phase']['live_witness']}"]
        goal=_inner_text(c["journal"]["goal"]); fail=_inner_text(c["journal"]["exit_conditions"])
        if goal: checks.append(f"NOT = {{ {goal} }}")
        if fail: checks.append(f"NOT = {{ {fail} }}")
        if q["mode"]=="exact": checks.append(f"var:{snap_value} = {q['value']}")
        restore=[]
        for notice in notice_queues:
            if notice==qvar: continue
            pvar=_queue_snapshot_name(ident,notice,"present"); vvar=_queue_snapshot_name(ident,notice,"value")
            restore += [f"remove_variable = {notice}",f"if = {{ limit = {{ has_variable = {pvar} }} set_variable = {{ name = {notice} value = var:{vvar} }} }}"]
            marker=notice.replace("_notice","_delivered")
            if notice.endswith("_blocked_12_notice") or notice.endswith("_blocked_36_notice"):
                mp=_queue_snapshot_name(ident,marker,"present"); mv=_queue_snapshot_name(ident,marker,"value")
                restore += [f"remove_variable = {marker}",f"if = {{ limit = {{ has_variable = {mp} }} set_variable = {{ name = {marker} value = var:{mv} }} }}"]
        body=" ".join([f"remove_variable = {qvar}",*restore,f"set_variable = {{ name = {served[c['arc']['slug']]} value = var:{roundv} }}",f"remove_variable = {reservation}",f"remove_variable = {timer}"])
        effects.append(f"{ack} = {{ if = {{ limit = {{ {' '.join(checks)} }} {body} }} }}")
    journal_scripts={}
    # Splice only proven sender limits and insert candidate-owned reservations before native source ops.
    for journal_id, journal_info in phases.items():
        journal=journal_info["journal"]; script=journal["script"]; binding=source_binding(journal_id,script)
        edits=[]
        for branch_index, group in branches_by_journal.get(journal_id,{}).items():
            branch=binding["branches"][branch_index]
            node,limit,trigger=_branch_node(script,branch)
            turns=" OR = { "+" ".join(f"{turn(c)} = yes" for c in group)+" }"
            edits.append((branch["limit_end"]-1,branch["limit_end"]-1," "+turns+" "))
            reserve_calls=" ".join(f"if = {{ limit = {{ {turn(c)} = yes }} ywc_v03_dmg_inline_reserve_{c['id']} = yes }}" for c in group)
            edits.append((branch["limit_end"],branch["limit_end"]," "+reserve_calls+" "))
            # The source queue removal moves to post-immediate ACK so failed trigger attempts remain retryable.
            for op in children(node):
                if op.key=="remove_variable" and isinstance(op.value,str) and any(op.value==c["queue"]["queue"] for c in group):
                    edits.append((op.start,op.end,""))
        for start,end,replacement in sorted(edits,reverse=True): script=script[:start]+replacement+script[end:]
        # Ensure scheduler state and reservation expiry are refreshed once in each native JE pulse.
        monthly=direct_values(parse_block(script),"on_monthly_pulse")[0]
        pulse=direct_values(children(monthly),"effect")[0]
        script=script[:pulse.value_start+1]+" ywc_v03_dmg_inline_prepare = yes "+script[pulse.value_start+1:]
        journal_scripts[journal_id]=script
    event_hooks={}; ack_hooks={}
    for event_id, group in candidates_by_event.items():
        event_hooks[event_id]=[dispatch(c) for c in group]
        hooks=[]
        for c in group:
            event=c["event"]; immediate=event["immediate"]
            hooks.append(f"ywc_v03_dmg_inline_ack_{c['id']}")
        ack_hooks[event_id]=hooks
    return {"triggers":"\n\n".join(triggers)+"\n","effects":"\n\n".join(effects)+"\n","event_hooks":event_hooks,"ack_hooks":ack_hooks,"guarded_immediate_events":sorted(event_hooks),"journal_scripts":journal_scripts,"live_witnesses":{j:p["phase"]["live_witness"] for j,p in phases.items()}}
