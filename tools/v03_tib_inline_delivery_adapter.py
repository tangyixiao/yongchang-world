"""Source-bound inline delivery adapter for the three TIB foundation arcs.

TIB keeps its authored monthly business logic intact. This module only adds a
private, per-invocation delivery protocol around those already-owned branches.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any

PREFIX = "ywc_v03_tib_inline"
SCHEMA = "v03.foundation_inline_adapter.v2"
EXPECTED_ARCS = {
    "v03_tib_grain_credit",
    "v03_tib_service_register",
    "v03_tib_shared_schools",
}
EFFECTS_AST_SHA256 = '32b91ecc2cb8ff8f0a1c94138a6ac1a684206d6fc7636d210aafc01b451c4d4a'
TRIGGERS_AST_SHA256 = 'a2a6e7e808b79797e699788f080e2bdaa76f4c87f0a07332cfee9a98229e62d6'


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
        raise ValueError("TIB source site must be one if/else_if branch")
    limits = direct_values(children(roots[0]), "limit")
    events = direct_values(children(roots[0]), "trigger_event")
    if len(limits) != 1 or len(events) != 1:
        raise ValueError("TIB sender branch needs one direct limit and event")
    found: list[dict[str, Any]] = []

    def walk(nodes: tuple[Any, ...], excluded: bool = False) -> None:
        for node in nodes:
            neg = excluded or node.key == "NOT"
            if isinstance(node.value, tuple):
                if node.key in {"OR", "XOR", "NOR"}:
                    raise ValueError(f"TIB sender contains unsupported queue Boolean {node.key}")
                walk(node.value, neg)
            elif not neg and node.key.startswith("var:ywc_tib_") and node.op == "=" and isinstance(node.value, str) and node.value.isdigit():
                queue = node.key[4:]
                if queue.endswith(("_pending_event", "_notice_12_event", "_notice_36_event")):
                    found.append({"queue": queue, "kind": "notice12" if queue.endswith("_notice_12_event") else "notice36" if queue.endswith("_notice_36_event") else "normal",
                                  "mode": "exact", "value": int(node.value)})
    walk(children(limits[0]))
    if len(found) != 1:
        raise ValueError(f"TIB sender must bind one positive exact native queue; got {found!r}")
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
        raise ValueError(f"{journal_id}: TIB requires one monthly pulse")
    effects = direct_values(children(monthly[0]), "effect")
    if len(effects) != 1:
        raise ValueError(f"{journal_id}: TIB monthly pulse needs one effect block")
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
            raise ValueError(f"{journal_id}: TIB sender AST binding lost")
        ordinal = nodes.index(node)
        if ordinal not in chain_at:
            raise ValueError(f"{journal_id}: TIB sender is outside an authored branch chain")
        result.append({**row, "statement_ordinal": ordinal, "chain_index": chain_at[ordinal],
                       "branch_kind": node.key, "candidates": _queue_candidates(script[node.start:node.end]),
                       "queue_exclusions": []})
    return result


def annotate_tib_catalog(catalog: dict[str, Any]) -> dict[str, Any]:
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
            suffix = journal["id"].removeprefix("ywc_je_v03_tib_")
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


def validate_tib_native_helper_source(effects_source: str, triggers_source: str) -> None:
    """Reject duplicate or AST-drifted native TIB helper definitions."""
    try:
        from tools.v03_inline_delivery_adapter import parse_block
    except ModuleNotFoundError:
        from v03_inline_delivery_adapter import parse_block

    for label, source, expected in (("effects", effects_source, EFFECTS_AST_SHA256),
                                    ("triggers", triggers_source, TRIGGERS_AST_SHA256)):
        try:
            nodes = parse_block("{\n" + source.lstrip("\ufeff") + "\n}")
        except Exception as exc:
            raise ValueError(f"TIB native helper {label} source is not parseable: {exc}") from exc
        names = [node.key for node in nodes]
        if len(names) != len(set(names)):
            raise ValueError(f"TIB native helper {label} source contains duplicate definitions")
        def canonical(node: Any) -> tuple[Any, ...]:
            value = [canonical(child) for child in node.value] if isinstance(node.value, tuple) else node.value
            return node.key, node.op, value
        digest = hashlib.sha256(repr([canonical(node) for node in nodes]).encode("utf-8")).hexdigest()
        if digest != expected:
            raise ValueError(f"TIB native helper {label} source ABI/AST drift")


JOURNAL_SHA256 = {'ywc_je_v03_tib_register_1': {'script': '1978b77d613dc4db4474bfdb3599393a607a2b94ca83c1d6f3e0e0b312ad3625', 'goal': '4ef08f0ae32db5ceb30ceece9256dc80ca88d988ccdd8d2fe21f2f04adc45baa', 'exit_conditions': '7db78b51e033fbe84b4c3c072f21db685ef7dd8b5260c65e7880812fef5343d6'}, 'ywc_je_v03_tib_register_2': {'script': '713a520603fe496303979464ffdaf650edb634dd03b6ac5a2f4c55551774cec1', 'goal': '37f0f6a065d10748e8b4607163ff09f8507d84c82ef300c1bba1891411e558bb', 'exit_conditions': '7db78b51e033fbe84b4c3c072f21db685ef7dd8b5260c65e7880812fef5343d6'}, 'ywc_je_v03_tib_register_3': {'script': 'a3c32814ecb67651a41d1afca3e7c7a3404e2486c95a3b55d8d21637e6b63e9d', 'goal': '431b11265476a7efa84ad66fa6926bb73dca2b63d77349c15fca38309c31f7c8', 'exit_conditions': '7db78b51e033fbe84b4c3c072f21db685ef7dd8b5260c65e7880812fef5343d6'}, 'ywc_je_v03_tib_grain_1': {'script': '6eb67a1ecbb1d2d946cc9756bd735996dba624c1b02fdf48a85faaa0193b4c23', 'goal': '48d111ec5e2130b4ab212b8bb0b2870a9701a11cf42783b514408d669ead09f9', 'exit_conditions': '273e44896c922c5999963ee7fa15d4b2a0ac14bb88427444dc889a54718aa933'}, 'ywc_je_v03_tib_grain_2': {'script': '089af2edf648d94f4654d3187b87e37016169c47a3229c1f104aba219adbdc8e', 'goal': 'b9b72b4a7ffa706e285f8d2b582dc01e1f8eb15b0b80b0dbd06716cbb4923543', 'exit_conditions': '273e44896c922c5999963ee7fa15d4b2a0ac14bb88427444dc889a54718aa933'}, 'ywc_je_v03_tib_schools_1': {'script': '606ccf73b63b6fab3e5086cf954bb30bf62a3815804c25a7381e3589437438ff', 'goal': '0e828351b7abfbb868926d6b3277216c7b22f539bffeafa0adbaadb7dfc8a9e5', 'exit_conditions': '0158d7599683c6649838a78d483c843178bae9c1fc9eb53503a54c8be6fd406a'}}


def _validate_catalog(catalog: dict[str, Any]) -> None:
    try:
        from tools.v03_inline_delivery_adapter import _kor_direct_adds
    except ModuleNotFoundError:
        from v03_inline_delivery_adapter import _kor_direct_adds

    if not isinstance(catalog, dict) or catalog.get("key") != "country_tib":
        raise ValueError("TIB inline adapter requires the TIB catalog")
    arcs = catalog.get("arcs")
    if (not isinstance(arcs, list) or len(arcs) != 3
            or any(not isinstance(arc, dict) or type(arc.get("slug")) is not str for arc in arcs)):
        raise ValueError("TIB inline adapter requires three well-formed foundation arcs")
    selected = [arc for arc in arcs if isinstance(arc, dict) and arc.get("era") == "foundation"]
    if len(selected) != 3 or {arc.get("slug") for arc in selected} != EXPECTED_ARCS:
        raise ValueError("TIB inline adapter requires exactly its three foundation arcs")
    witnesses: set[str] = set()
    all_events: set[str] = set()
    branches_seen: set[tuple[str, int]] = set()
    all_sources = []
    for arc in selected:
        adapter = arc.get("inline_delivery_adapter")
        if not isinstance(adapter, dict) or set(adapter) != {"schema", "live_phases", "branches", "direct_adds"} or adapter.get("schema") != SCHEMA:
            raise ValueError(f"{arc.get('slug')}: strict v2 inline metadata required")
        _int_tree(adapter, arc.get("slug", "arc"))
        journals = arc.get("journals")
        events = arc.get("events")
        expected_counts = {"v03_tib_grain_credit": (2, 8), "v03_tib_service_register": (3, 10),
                           "v03_tib_shared_schools": (1, 6)}[arc["slug"]]
        if not isinstance(journals, list) or len(journals) != expected_counts[0] or not isinstance(events, list) or len(events) != expected_counts[1]:
            raise ValueError(f"{arc['slug']}: TIB journal/event inventory drift")
        phases = adapter["live_phases"]
        if not isinstance(phases, list) or len(phases) != len(journals):
            raise ValueError(f"{arc['slug']}: every native JE needs one phase witness")
        for phase, journal in zip(phases, journals):
            if (not isinstance(journal, dict) or type(journal.get("id")) is not str
                    or any(type(journal.get(field)) is not str for field in ("script", "goal", "exit_conditions"))):
                raise ValueError("TIB journals require literal identity and complete source strings")
            expected = JOURNAL_SHA256.get(journal.get("id"))
            if expected is None or any(hashlib.sha256(journal[field].encode("utf-8")).hexdigest() != digest for field, digest in expected.items()):
                raise ValueError("TIB authored journal source drift")
            required = {"journal", "live_witness", "source_script_sha256", "goal_sha256", "exit_sha256"}
            if not isinstance(phase, dict) or set(phase) != required or phase["journal"] != journal["id"]:
                raise ValueError(f"{arc['slug']}: malformed TIB phase binding")
            for field, source_field in (("source_script_sha256", "script"), ("goal_sha256", "goal"), ("exit_sha256", "exit_conditions")):
                digest = hashlib.sha256(journal[source_field].encode("utf-8")).hexdigest()
                if type(phase[field]) is not str or phase[field] != digest:
                    raise ValueError(f"{journal['id']}: TIB source {source_field} drift")
            witness = phase["live_witness"]
            if type(witness) is not str or witness != PREFIX + "_live_" + journal["id"].removeprefix("ywc_je_v03_tib_") or witness in witnesses:
                raise ValueError(f"{journal['id']}: invalid or duplicate TIB live witness")
            witnesses.add(witness)
        for event in events:
            if (not isinstance(event, dict) or type(event.get("id")) is not str
                    or any(type(event.get(field)) is not str for field in ("trigger", "immediate"))
                    or not isinstance(event.get("options"), list)
                    or any(not isinstance(option, dict) or type(option.get("key")) is not str
                           or type(option.get("effect")) is not str for option in event["options"])):
                raise ValueError("TIB events require literal identity, source strings and source options")
        if adapter["direct_adds"] != _kor_direct_adds(arc):
            raise ValueError(f"{arc['slug']}: TIB direct-add binding drift")
        for event in events:
            event_id = event.get("id") if isinstance(event, dict) else None
            if not isinstance(event_id, str) or event_id in all_events:
                raise ValueError(f"{arc['slug']}: duplicate or invalid TIB event identity")
            all_events.add(event_id)
            immediate = event.get("immediate")
            if type(immediate) is not str:
                raise ValueError(f"{event_id}: native immediate must remain raw source text")
            try:
                from tools.v03_inline_delivery_adapter import parse_block
            except ModuleNotFoundError:
                from v03_inline_delivery_adapter import parse_block
            trigger = parse_block(event.get("trigger", ""))
            expected_trigger = parse_block("{ c:TIB ?= this ywc_v03_can_deliver_major = yes }")
            if _ast_rows(trigger) != _ast_rows(expected_trigger):
                raise ValueError(f"{event_id}: native trigger layout drift")
            body = parse_block(immediate)
            if len(body) != 1 or body[0].key != "ywc_v03_mark_major_delivered" or body[0].op != "=" or body[0].value != "yes":
                raise ValueError(f"{event_id}: native immediate layout drift")
        expected_rows = []
        for journal in journals:
            expected_rows.extend((journal["id"], row) for row in _binding(journal["id"], journal["script"]))
        records = adapter["branches"]
        if not isinstance(records, list) or len(records) != len(expected_rows):
            raise ValueError(f"{arc['slug']}: all TIB native sender branches must be bound")
        required = {"journal", "branch_index", "statement_ordinal", "chain_index", "branch_kind", "event",
                    "branch_sha256", "limit_sha256", "chain_prior", "chain_sha256", "candidates", "queue_exclusions"}
        for proof, (jid, source) in zip(records, expected_rows):
            if not isinstance(proof, dict) or set(proof) != required:
                raise ValueError(f"{arc['slug']}/{jid}: malformed TIB source binding")
            checks = {"journal": jid, "branch_index": source["branch_index"],
                      "statement_ordinal": source["statement_ordinal"], "chain_index": source["chain_index"],
                      "branch_kind": source["branch_kind"], "event": source["event"],
                      "branch_sha256": source["sha256"], "limit_sha256": source["limit_sha256"],
                      "chain_prior": source["chain_prior"], "chain_sha256": source["chain_sha256"],
                      "candidates": source["candidates"], "queue_exclusions": source["queue_exclusions"]}
            if any(proof.get(field) != expected for field, expected in checks.items()):
                raise ValueError(f"{arc['slug']}/{jid}: raw TIB branch, priority chain or queue drift")
            for key in ("branch_index", "statement_ordinal", "chain_index"):
                if type(proof[key]) is not int:
                    raise ValueError(f"{jid}: {key} must be an integer")
            identity = (jid, proof["branch_index"])
            if identity in branches_seen:
                raise ValueError(f"{jid}: duplicate TIB branch identity")
            branches_seen.add(identity)
            candidate = proof["candidates"][0]
            if (not isinstance(candidate, dict) or set(candidate) != {"queue", "kind", "mode", "value"}
                or type(candidate["value"]) is not int or candidate["mode"] != "exact"
                or candidate["kind"] not in {"normal", "notice12", "notice36"}):
                raise ValueError(f"{jid}: malformed TIB queue candidate")
            if proof["event"] not in {event["id"] for event in events}:
                raise ValueError(f"{jid}: unowned TIB event binding")
            all_sources.append((arc, next(j for j in journals if j["id"] == jid), proof))
    if len(witnesses) != 6 or len(all_events) != 24 or len(all_sources) != 58:
        raise ValueError("TIB adapter must bind six phases, 24 events and 58 source senders")
    if sum(row[2]["candidates"][0]["kind"] == "normal" for row in all_sources) != 40:
        raise ValueError("TIB adapter must bind 40 normal and eighteen notice senders")


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
        if node.key.startswith("var:ywc_tib_"):
            refs.add(node.key[4:])
        elif node.key == "has_variable" and isinstance(node.value, str) and node.value.startswith("ywc_tib_"):
            refs.add(node.value)
        elif node.key == "remove_variable" and isinstance(node.value, str) and node.value.startswith("ywc_tib_"):
            refs.add(node.value)
        elif node.key in {"set_variable", "change_variable", "clamp_variable"} and isinstance(node.value, tuple):
            refs.update(child.value for child in children(node) if child.key == "name" and isinstance(child.value, str) and child.value.startswith("ywc_tib_"))
        if isinstance(node.value, tuple):
            refs.update(_node_refs(children(node)))
    return refs




def _set(name: str, value: str | int) -> str:
    return f"set_variable = {{ name = {name} value = {value} }}"


def _render_adapter(catalog: dict[str, Any]) -> dict[str, Any]:
    try:
        from tools.v03_inline_delivery_adapter import children, direct_values, parse_block, render_node
    except ModuleNotFoundError:
        from v03_inline_delivery_adapter import children, direct_values, parse_block, render_node
    _validate_catalog(catalog)
    arcs = [arc for arc in catalog["arcs"] if arc.get("era") == "foundation"]
    rows = []
    live = {phase["journal"]: phase["live_witness"] for arc in arcs
            for phase in arc["inline_delivery_adapter"]["live_phases"]}
    native_names: set[str] = set()
    for arc in arcs:
        for journal in arc["journals"]:
            for branch in _binding(journal["id"], journal["script"]):
                source = journal["script"][branch["start"]:branch["end"]]
                native_branch = parse_block("{ " + source + " }")[0]
                native_names.update(_node_refs((native_branch,)))
                rows.append({"id": len(rows) + 1, "journal": journal,
                             "branch": branch, "native_branch": native_branch})
    native_names = sorted(native_names)
    # The authored senders read/write all nine queues and three last-delivered
    # markers. Freeze their presence and scalar value after the full native pre.
    if len(native_names) != 12:
        raise ValueError("TIB native queue/marker snapshot inventory drift")
    reservation = PREFIX + "_reservation"
    epoch = PREFIX + "_reservation_epoch"
    current = PREFIX + "_epoch"
    initialized = PREFIX + "_epoch_initialized"
    timer = PREFIX + "_timer"
    effects: list[str] = []
    triggers: list[str] = []
    journal_scripts: dict[str, str] = {}
    event_hooks: dict[str, list[str]] = {}
    inline_proofs: dict[str, list[str]] = {}
    ack_hooks: dict[str, list[str]] = {}
    row_private: dict[int, list[str]] = {}
    replacements: dict[str, list[tuple[int, int, str]]] = {}

    def helper(suffix: str, ident: int) -> str:
        return f"{PREFIX}_{suffix}_{ident}"

    def snapshot_pair(ident: int, native: str) -> tuple[str, str]:
        stem = native.removeprefix("ywc_tib_")
        return tuple(f"{PREFIX}_snapshot_{ident}_{stem}_{kind}"
                     for kind in ("present", "value"))

    def snapshot_checks(ident: int) -> str:
        checks = []
        for native in native_names:
            present, value = snapshot_pair(ident, native)
            checks.append("OR = { "
                f"AND = {{ has_variable = {native} has_variable = {present} has_variable = {value} "
                f"var:{present} = 1 var:{native} = var:{value} }} "
                f"AND = {{ NOT = {{ has_variable = {native} }} has_variable = {present} "
                f"has_variable = {value} var:{present} = 0 var:{value} = 0 }} }}")
        return " ".join(checks)

    def owned_effect(name: str, guard: str, commands: str) -> None:
        effects.append(f"{name} = {{ if = {{ limit = {{ {guard} }} {commands} }} }}")

    for row in rows:
        ident, journal, branch, native_branch = (row[k] for k in ("id", "journal", "branch", "native_branch"))
        candidate = branch["candidates"][0]
        queue, value = candidate["queue"], candidate["value"]
        witness = live[journal["id"]]
        candidate_epoch = helper("candidate_epoch", ident)
        boundary, boundary_epoch = helper("source_boundary", ident), helper("source_boundary_epoch", ident)
        source_receipt, source_epoch = helper("source_completed", ident), helper("source_completed_epoch", ident)
        body_receipt, body_epoch = helper("body_completed", ident), helper("body_completed_epoch", ident)
        callback_fields = [helper(suffix, ident) for suffix in ("callback", "callback_candidate", "callback_epoch", "callback_queue")]
        private = [candidate_epoch, boundary, boundary_epoch, source_receipt, source_epoch, body_receipt, body_epoch, *callback_fields]
        private += [name for native in native_names for name in snapshot_pair(ident, native)]
        row_private[ident] = private
        fields = list(children(native_branch))
        limit = direct_values(fields, "limit")[0]
        native_limit = " ".join(_render_nodes(children(limit)))
        trigger_at = next(index for index, node in enumerate(fields) if node.key == "trigger_event")
        if fields[trigger_at+1:]:
            raise ValueError(f"TIB candidate {ident}: unsupported nonempty native postfragment")
        # Missing or damaged identity history is never a fresh allocator.
        # This presence-only marker survives custody expiry and ACK; it does
        # not identify an occurrence or substitute for either receipt pair.
        counter_available = ("OR = { "
            f"AND = {{ NOT = {{ has_variable = {initialized} }} NOT = {{ has_variable = {current} }} }} "
            f"AND = {{ has_variable = {current} var:{current} > 0 }} }}")
        admission = (f"has_journal_entry = {journal['id']} has_variable = {witness} var:{witness} = 1 "
                     f"NOT = {{ has_variable = {reservation} }} NOT = {{ has_variable = {timer} }} {native_limit} {counter_available}")
        triggers.append(f"{helper('candidate', ident)} = {{ {admission} }}")
        reserve = [f"remove_variable = {name}" for name in private]
        reserve += [f"if = {{ limit = {{ has_variable = {current} var:{current} > 0 }} change_variable = {{ name = {current} add = 1 }} }}",
                    f"if = {{ limit = {{ NOT = {{ has_variable = {initialized} }} NOT = {{ has_variable = {current} }} }} {_set(current, 1)} }}",
                    _set(initialized, 1),
                    _set(epoch, f"var:{current}"), _set(candidate_epoch, f"var:{epoch}"),
                    _set(reservation, ident), f"set_variable = {{ name = {timer} value = 1 days = 90 }}"]
        owned_effect(helper("reserve", ident), f"{helper('candidate', ident)} = yes", " ".join(reserve))
        invocation = (f"exists = scope:{PREFIX}_dispatch_candidate scope:{PREFIX}_dispatch_candidate = {ident} "
                      f"exists = scope:{PREFIX}_dispatch_epoch scope:{PREFIX}_dispatch_epoch = var:{epoch}")
        owner = (f"has_variable = {reservation} var:{reservation} = {ident} "
                 f"has_variable = {current} var:{current} > 0 "
                 f"has_variable = {epoch} var:{epoch} > 0 var:{epoch} = var:{current} "
                 f"has_variable = {candidate_epoch} var:{candidate_epoch} > 0 var:{candidate_epoch} = var:{epoch} {invocation}")
        triggers.append(f"{helper('source_boundary_owner', ident)} = {{ {owner} }}")
        live_owner = (f"has_journal_entry = {journal['id']} has_variable = {witness} var:{witness} = 1 "
                      f"has_variable = {timer} var:{timer} = 1 {owner} var:{queue} = {value}")
        snapshots = snapshot_checks(ident)
        common = f"{live_owner} {snapshots}"
        reached = (f"has_variable = {boundary} var:{boundary} = {ident} "
                   f"has_variable = {boundary_epoch} var:{boundary_epoch} = var:{epoch}")
        source_proof = (f"has_variable = {source_receipt} var:{source_receipt} = 1 "
                        f"has_variable = {source_epoch} var:{source_epoch} = var:{epoch}")
        body_proof = (f"has_variable = {body_receipt} var:{body_receipt} = 1 "
                      f"has_variable = {body_epoch} var:{body_epoch} = var:{epoch}")
        dispatch_boundary = ("OR = { "
            f"AND = {{ NOT = {{ has_variable = {boundary} }} NOT = {{ has_variable = {boundary_epoch} }} "
            f"NOT = {{ has_variable = {source_receipt} }} NOT = {{ has_variable = {source_epoch} }} }} "
            f"AND = {{ {reached} {source_proof} }} }}")
        triggers.append(f"{helper('dispatch', ident)} = {{ {common} "
                        f"NOT = {{ has_variable = {body_receipt} }} NOT = {{ has_variable = {body_epoch} }} {dispatch_boundary} }}")
        owned_effect(helper("source_return", ident), f"{common} {reached}",
            f"{_set(source_receipt, 1)} {_set(source_epoch, 'var:'+epoch)} {helper('join', ident)} = yes")
        owned_effect(helper("body_return", ident), common,
            f"{_set(body_receipt, 1)} {_set(body_epoch, 'var:'+epoch)} {helper('join', ident)} = yes")
        callback_values = (1, ident, "var:"+epoch, "var:"+queue)
        owned_effect(helper("callback", ident), common,
            " ".join(_set(name, value) for name, value in zip(callback_fields, callback_values)) + f" {helper('join', ident)} = yes")
        callback_guard = " ".join(f"has_variable = {name} var:{name} = {value}"
                                  for name, value in zip(callback_fields, callback_values))
        complete = f"{common} {reached} {source_proof} {body_proof} {callback_guard}"
        owned_effect(helper("join", ident), complete, f"{helper('ack', ident)} = yes")
        # Keep completed receipt values available for audit; removing custody
        # makes them inert. A new reservation clears them before dispatch.
        owned_effect(helper("ack", ident), complete,
                     " ".join(f"remove_variable = {name}" for name in (queue, timer, reservation, boundary, boundary_epoch)))
        event_hooks.setdefault(branch["event"], []).append(helper("dispatch", ident))
        inline_proofs.setdefault(branch["event"], []).append(helper("body_return", ident)+" = yes")
        ack_hooks.setdefault(branch["event"], []).append(helper("callback", ident))

        # Preserve the original branch kind/priority and every native command,
        # deferring only the selected clear. Capture P after complete native pre.
        output = [f"{native_branch.key} = {{ limit = {{ {native_limit} {helper('candidate', ident)} = yes }}",
                  f"{helper('reserve', ident)} = yes"]
        selected_clears = 0
        for index, node in enumerate(fields):
            if node.key == "limit":
                continue
            if index == trigger_at:
                for native in native_names:
                    present, captured = snapshot_pair(ident, native)
                    output += [_set(present, 0), _set(captured, 0),
                        f"if = {{ limit = {{ has_variable = {native} }} {_set(present, 1)} {_set(captured, 'var:'+native)} }}"]
                output += [f"save_scope_value_as = {{ name = {PREFIX}_dispatch_candidate value = var:{reservation} }}",
                           f"save_scope_value_as = {{ name = {PREFIX}_dispatch_epoch value = var:{epoch} }}"]
            if node.key == "remove_variable" and node.value == queue:
                selected_clears += 1
                continue
            output.append(_render_nodes((node,))[0])
        if selected_clears != 1:
            raise ValueError(f"TIB candidate {ident}: expected one selected native clear")
        output += [f"if = {{ limit = {{ {helper('source_boundary_owner', ident)} = yes }} {_set(boundary, ident)} {_set(boundary_epoch, 'var:'+epoch)} }}",
                   f"{helper('source_return', ident)} = yes", "}"]
        replacements.setdefault(journal["id"], []).append((branch["start"], branch["end"], " ".join(output)))

    for arc in arcs:
        for journal in arc["journals"]:
            script = journal["script"]
            for start, end, text in reversed(replacements[journal["id"]]):
                script = script[:start] + text + script[end:]
            monthly = direct_values(parse_block(script), "on_monthly_pulse")[0]
            effect = direct_values(children(monthly), "effect")[0]
            at = effect.value_start + 1
            script = script[:at] + f" {PREFIX}_prepare = yes " + script[at:]
            journal_scripts[journal["id"]] = script
    # Expiry never consumes native queues, rolls back marker writes, or clears
    # phase witnesses. Keep the monotonic counter so old numeric contexts cannot
    # service a subsequent same-value reservation.
    cleanup = [reservation, epoch, *[name for names in row_private.values() for name in names]]
    owned_effect(PREFIX+"_prepare", f"has_variable = {reservation} NOT = {{ has_variable = {timer} }}",
                 " ".join(f"remove_variable = {name}" for name in cleanup))
    return {"effects": "\n".join(effects)+"\n", "triggers": "\n".join(triggers)+"\n",
            "journal_scripts": journal_scripts, "event_hooks": event_hooks,
            "inline_proofs": inline_proofs, "ack_hooks": ack_hooks,
            "live_witnesses": live, "guarded_immediate_events": sorted(event_hooks),
            "safe_comment_boundaries": True}


def _render_nodes(nodes: Any) -> list[str]:
    """Canonical source AST rendering keeps legal comments out of joins."""
    return [f"{node.key} {node.op} " + ("{ " + " ".join(_render_nodes(node.value)) + " }"
            if isinstance(node.value, tuple) else node.value) for node in nodes]


def render_tib_inline_country_adapters(catalog: dict[str, Any]) -> dict[str, Any]:
    return _render_adapter(catalog)


def validate_tib_inline_catalog(catalog: dict[str, Any]) -> None:
    _validate_catalog(catalog)
