"""Source-backed LAN history/admission fixture and the first inline-contract RED gate.

The interpreter executes authored LAN source. It is not a Victoria 3 engine.
"""
import json
import itertools
import unittest
from pathlib import Path

from tests.clausewitz_harness import parse
from tests.test_v03_lan_foundation import StrictLanRuntimeWorld
from tools.v03_inline_delivery_adapter import render_inline_country_adapters, _queue_snapshot_name

ROOT = Path(__file__).resolve().parents[1]
FX_PATHS = [
    "yongchang_world/common/scripted_effects/ywc_v03_lan_effects.txt",
    "yongchang_world/common/scripted_effects/ywc_v03_effects.txt",
    "yongchang_world/common/scripted_effects/ywc_campaign_effects.txt",
    "yongchang_world/common/scripted_effects/ywc_flavor_effects.txt",
    "yongchang_world/common/scripted_effects/ywc_shared_effects.txt",
]
TRIGGER_PATHS = [
    "yongchang_world/common/scripted_triggers/ywc_v03_lan_triggers.txt",
    "yongchang_world/common/scripted_triggers/ywc_v03_triggers.txt",
]
EVENT_PATHS = ["yongchang_world/events/ywc_kor_lan_nmg_events.txt",
               "yongchang_world/events/ywc_large_campaign_events.txt",
               "yongchang_world/events/ywc_v03_country_lan_events.txt"]
JOURNAL_PATHS = ["yongchang_world/common/journal_entries/ywc_lan.txt",
                 "yongchang_world/common/journal_entries/ywc_v03_country_lan_journal.txt"]
HISTORY_PATHS = ["yongchang_world/common/history/countries/ywc_content_starts.txt",
                 "yongchang_world/common/history/diplomacy/ywc_inner_asia_diplomacy.txt"]
CATALOG_PATH = ROOT / "data/content/v03/countries/lan.json"
ARC_ORDER = ("v03_lan_mine_accounts", "v03_lan_river_compacts", "v03_lan_work_accident_fund")
LEGACY_EVENTS = (("ywc_lan.7", "ywc_lan.7.a", 30),
                 ("ywc_lan.100", "ywc_lan.100.a", 60),
                 ("ywc_lan.101", "ywc_lan.101.a", 180),
                 ("ywc_lan.102", "ywc_lan.102.a", 300),
                 ("ywc_lan.103", "ywc_lan.103.a", 420),
                 ("ywc_lan.104", "ywc_lan.104.b", 540))


def _read(path):
    return (ROOT / path).read_text(encoding="utf-8-sig")


def _defs(paths):
    result = {}
    for path in paths:
        for key, _, body in parse(_read(path)):
            if key in result:
                raise AssertionError(f"native definition collision: {key} in {path}")
            result[key] = body
    return result


def _merge_script_definitions(paths, optional_paths=()):
    sources = list(paths) + [path for path in optional_paths if (ROOT / path).is_file()]
    merged = {}
    for path in sources:
        for key, _, body in parse(_read(path)):
            if not isinstance(body, list):
                continue
            if key in merged:
                raise AssertionError(f"script definition collision: {key} in {path}")
            merged[key] = body
    return merged


def _fields(nodes):
    return {key: value for key, _, value in nodes}


def _effects(nodes):
    ignored = {"name", "ai_chance", "default_option", "trigger", "custom_tooltip"}
    return [node for node in nodes if node[0] not in ignored]


class LanActualWorld(StrictLanRuntimeWorld):
    """Strict existing LAN interpreter plus the one documented engine fact."""
    def validate_condition(self, node, seen=frozenset()):
        key, comparison, value = node
        if key == "is_subject":
            assert comparison == "=" and value in ("yes", "no"), node
            return
        if key in self.trigger_defs:
            assert comparison == "=" and value in ("yes", "no") and key not in seen, node
            for child in self.trigger_defs[key]:
                self.validate_condition(child, seen | {key})
            return
        if key == "has_journal_entry":
            assert (comparison == "=" and isinstance(value, str)
                    and value.startswith("ywc_je_")
                    and value.removeprefix("ywc_je_").replace("_", "").isalnum()), node
            return
        super().validate_condition(node, seen)

    def condition(self, node, tag):
        key, comparison, value = node
        if key == "is_subject":
            assert comparison == "=" and value in ("yes", "no"), node
            return bool(self.countries[tag]["is_subject"]) == (value == "yes")
        if key in self.trigger_defs:
            self.validate_condition(node)
            return self.conditions(self.trigger_defs[key], tag) == (value == "yes")
        if key == "has_journal_entry":
            self.validate_condition(node)
            return value in self.active_journal_ids.get(tag, set())
        return super().condition(node, tag)


def _fresh_three_arcs(order=ARC_ORDER, is_subject=True):
    """Return world, engine-owned active-JE bookkeeping, and authored definitions."""
    source = _read("yongchang_world/common/history/diplomacy/ywc_inner_asia_diplomacy.txt")
    dip = _defs(["yongchang_world/common/history/diplomacy/ywc_inner_asia_diplomacy.txt"])
    assert "DIPLOMACY" in dip
    # Authored SHU -> LAN tributary is the positive subject fact's provenance.
    root = dip["DIPLOMACY"]
    shu = next(body for key, _, body in root if key == "c:SHU")
    pact = next(body for key, _, body in shu if key == "create_diplomatic_pact"
                 and _fields(body).get("country") == "c:LAN")
    assert _fields(pact).get("type") == "tributary" and source
    effect_defs = _merge_script_definitions(FX_PATHS,
        ["yongchang_world/common/scripted_effects/ywc_v03_delivery_lan_effects.txt"])
    trigger_defs = _merge_script_definitions(TRIGGER_PATHS,
        ["yongchang_world/common/scripted_triggers/ywc_v03_delivery_lan_triggers.txt"])
    fx_paths = FX_PATHS + (["yongchang_world/common/scripted_effects/ywc_v03_delivery_lan_effects.txt"]
                           if (ROOT / "yongchang_world/common/scripted_effects/ywc_v03_delivery_lan_effects.txt").is_file() else [])
    trigger_paths = TRIGGER_PATHS + (["yongchang_world/common/scripted_triggers/ywc_v03_delivery_lan_triggers.txt"]
                                     if (ROOT / "yongchang_world/common/scripted_triggers/ywc_v03_delivery_lan_triggers.txt").is_file() else [])
    fx = "\n".join(_read(path) for path in fx_paths)
    triggers = "\n".join(_read(path) for path in trigger_paths)
    world = LanActualWorld(fx, triggers, {"LAN": {"is_subject": is_subject}})
    world.active_journal_ids = {"LAN": set()}
    world.journal_defs = _defs(JOURNAL_PATHS)
    world.event_defs = {key: body for key, body in _merge_script_definitions(EVENT_PATHS).items()
                        if key.startswith("ywc_lan.")}
    generated_lan_events = [key for key in world.event_defs if key.startswith("ywc_lan.")
                            and 1000 <= int(key.rsplit(".", 1)[1]) <= 1027]
    assert len(generated_lan_events) == 24, ("formal LAN event file must provide 24 arc events", len(generated_lan_events))
    journals = world.journal_defs
    country_history = _defs(["yongchang_world/common/history/countries/ywc_content_starts.txt"])
    lan = next(body for key, _, body in country_history["COUNTRIES"] if key == "c:LAN")
    before = len(world.journals)
    world.execute(lan, "LAN")
    added = [body for tag, body in world.journals[before:] if tag == "LAN"]
    legacy_id = "ywc_je_flavor_lan_charter_1"
    assert sum(_fields(body).get("type") == legacy_id for body in added) == 1
    active = {legacy_id: {"status": "active", "origin": "country_history_add"}}
    world.active_journal_ids["LAN"].add(legacy_id)
    legacy = journals[legacy_id]
    pulse = next(body for key, _, body in legacy if key == "on_monthly_pulse")
    pulse_effect = next(body for key, _, body in pulse if key == "effect")
    complete = next(body for key, _, body in legacy if key == "complete")
    fail = next(body for key, _, body in legacy if key == "fail")
    dispatch = {event: option for event, option, _ in LEGACY_EVENTS}
    by_id = world.event_defs
    observations = []
    for day in range(30, 541, 30):
        world.advance_days(30)
        world.execute(pulse_effect, "LAN")
        emitted = [event for tag, event in world.events if tag == "LAN"]
        world.events.clear()
        for event_id in emitted:
            if event_id not in dispatch:
                raise AssertionError(("unexpected_legacy_source_popup", day, event_id))
            body = by_id[event_id]
            event_trigger = next((value for key, _, value in body if key == "trigger"), None)
            event_legal = event_trigger is None or world.conditions(event_trigger, "LAN")
            assert event_legal, (event_id, day, "legacy event trigger false")
            immediate = next((value for key, _, value in body if key == "immediate"), [])
            before_event = dict(world.countries["LAN"])
            if immediate:
                world.execute(immediate, "LAN")
            after_immediate = dict(world.countries["LAN"])
            option_id = dispatch[event_id]
            option = next(value for key, _, value in body if key == "option"
                          and _fields(value).get("name") == option_id)
            gate = next((value for key, _, value in option if key == "trigger"), [])
            legal = not gate or world.conditions(gate, "LAN")
            assert legal, (event_id, option_id, "source option is illegal")
            world.execute(_effects(option), "LAN")
            observations.append({"day": day, "event": event_id, "event_trigger_legal": event_legal,
                                 "immediate_present": bool(immediate), "immediate_before": before_event,
                                 "immediate_after": after_immediate, "option": option_id,
                                 "option_legal": legal})
            done, failed = world.conditions(complete, "LAN"), world.conditions(fail, "LAN")
            assert not (done and failed)
            if done or failed:
                active[legacy_id]["status"] = "completed" if done else "failed"
                break
        if active[legacy_id]["status"] != "active":
            break
    assert [row["event"] for row in observations] == [event for event, _, _ in LEGACY_EVENTS]
    assert active[legacy_id]["status"] == "completed"
    legacy_complete = world.conditions(complete, "LAN")
    legacy_fail = world.conditions(fail, "LAN")
    assert legacy_complete and not legacy_fail, (legacy_complete, legacy_fail)

    world.run("ywc_v03_initialize_country", "LAN")
    assert world.countries["LAN"].get("ywc_v03_active_arc_count") == 0
    assert world.countries["LAN"].get("ywc_v03_visible_task_count") == 0
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    # This fixture proves the original three arcs and six native source orders.
    # Company-public participation has its own real-fact source-order scenario.
    native = {arc["slug"]: journals[arc["journals"][0]["id"]]
              for arc in catalog["arcs"] if arc["era"] == "foundation"}
    admissions = []
    for slug in order:
        definition = native[slug]
        shown = next(body for key, _, body in definition if key == "is_shown_when_inactive")
        possible = next(body for key, _, body in definition if key == "possible")
        immediate = next(body for key, _, body in definition if key == "immediate")
        eligible = world.conditions(shown, "LAN") and world.conditions(possible, "LAN")
        assert eligible, (slug, "not source-shown and possible")
        world.execute(immediate, "LAN")
        entry_id = next(arc["journals"][0]["id"] for arc in catalog["arcs"] if arc["slug"] == slug)
        active[entry_id] = {"status": "active", "origin": "native_journal_immediate"}
        world.active_journal_ids["LAN"].add(entry_id)
        world.journals.append(("LAN", [("type", "=", entry_id)]))
        admissions.append({"slug": slug, "entry": entry_id, "shown": True, "possible": True,
                           "count": world.countries["LAN"].get("ywc_v03_active_arc_count"),
                           "visible": world.countries["LAN"].get("ywc_v03_visible_task_count")})
    assert [row["count"] for row in admissions] == [1, 2, 3]
    assert [row["visible"] for row in admissions] == [1, 2, 3]
    return world, active, native, {"legacy_events": observations, "admissions": admissions,
                                   "legacy_complete": legacy_complete, "legacy_fail": legacy_fail}


class LanHistoryAndAdmissionActualTest(unittest.TestCase):
    def test_native_history_and_source_joint_admission_for_subject_and_counterfactual(self):
        for subject in (True, False):
            with self.subTest(is_subject=subject):
                world, active, native, evidence = _fresh_three_arcs(is_subject=subject)
                self.assertEqual([row["event"] for row in evidence["legacy_events"]],
                                 [event for event, _, _ in LEGACY_EVENTS])
                self.assertEqual([row["day"] for row in evidence["legacy_events"]],
                                 [day for _, _, day in LEGACY_EVENTS])
                self.assertEqual(world.countries["LAN"].get("ywc_campaign_lan_c1_outcome"), 2)
                self.assertIn("ywc_je_flavor_lan_charter_1_resolved", world.countries["LAN"])
                self.assertTrue(evidence["legacy_complete"])
                self.assertFalse(evidence["legacy_fail"])
                self.assertEqual(list(active.values())[0]["status"], "completed")
                self.assertEqual([row["count"] for row in evidence["admissions"]], [1, 2, 3])
                self.assertEqual(len(native), 3)
                self.assertTrue(world.conditions(next(body for key, _, body in native[ARC_ORDER[0]] if key == "complete"), "LAN") is False)
                self.assertTrue(world.conditions(next(body for key, _, body in native[ARC_ORDER[0]] if key == "fail"), "LAN") is False)


class LanFirstPopupInlineContractRedTest(unittest.TestCase):
    def test_actual_native_first_popup_requires_reservation_epoch_queue_and_dispatch_guard(self):
        for order in itertools.permutations(ARC_ORDER):
            with self.subTest(order=order):
                world, _, native, _ = _fresh_three_arcs(order)
                slug = order[0]
                body = native[slug]
                pulse = next(value for key, _, value in body if key == "on_monthly_pulse")
                effect = next(value for key, _, value in pulse if key == "effect")
                world.advance_days(30)
                before = len(world.events)
                world.execute(effect, "LAN")
                event = next((event for tag, event in world.events[before:] if tag == "LAN"), None)
                self.assertIsNotNone(event, f"native first pulse produced no popup for {slug}")
                event_body = world.event_defs[event]
                event_trigger = next((value for key, _, value in event_body if key == "trigger"), [])
                self.assertTrue(world.conditions(event_trigger, "LAN"),
                                f"native event trigger rejected actual first popup {event}")
                country = world.countries["LAN"]
                prefix = "ywc_v03_lan_inline"
                # The deliberate current RED is absence of the protocol's actual reservation.
                self.assertIn(prefix + "_reservation", country,
                              "native popup has no real LAN candidate reservation")
                reservation = country[prefix + "_reservation"]
                self.assertIsInstance(reservation, (int, float))
                self.assertGreater(reservation, 0)
                epoch = country.get(prefix + "_reservation_epoch")
                self.assertIsNotNone(epoch, "reservation has no global epoch")
                self.assertGreater(epoch, 0, "reservation epoch must be positive")
                catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
                try:
                    rendered = render_inline_country_adapters(catalog)
                except (ValueError, KeyError, AssertionError) as exc:
                    self.fail(f"LAN v2 metadata is not consumable by the formal renderer: {exc}")
                candidate_rows = []
                for arc in catalog["arcs"]:
                    adapter = arc.get("inline_delivery_adapter")
                    self.assertIsInstance(adapter, dict, f"{arc['slug']} lacks per-arc v2 metadata")
                    for branch in adapter["branches"]:
                        candidate_rows.extend((arc, branch, candidate)
                                              for candidate in branch["candidates"])
                candidate_id = int(reservation)
                self.assertLessEqual(candidate_id, len(candidate_rows))
                arc, branch, candidate = candidate_rows[candidate_id - 1]
                self.assertEqual(branch["event"], event)
                candidate_epoch = country.get(f"{prefix}_candidate_epoch_{candidate_id}")
                self.assertIsNotNone(candidate_epoch)
                self.assertGreater(candidate_epoch, 0)
                self.assertEqual(candidate_epoch, epoch)
                queue = candidate["queue"]
                present_name = _queue_snapshot_name(candidate_id, queue, "present", prefix)
                value_name = _queue_snapshot_name(candidate_id, queue, "value", prefix)
                self.assertIn(present_name, country)
                self.assertEqual(country[present_name], 1)
                self.assertIn(value_name, country)
                if candidate["mode"] == "exact":
                    self.assertEqual(country[value_name], candidate["value"])
                # For presence queues value 0 remains a valid captured value; presence is proven separately.
                dispatch_guards = rendered["event_hooks"][event]
                selected_guard = f"{prefix}_dispatch_{candidate_id}"
                self.assertIn(selected_guard, dispatch_guards,
                              "selected reservation candidate is not bound to this event's dispatch guards")
                guard = selected_guard
                self.assertIn(guard, world.trigger_defs,
                              f"renderer dispatch helper {guard} is not loaded into the actual trigger set")
                self.assertTrue(world.conditions(world.trigger_defs[guard], "LAN"),
                                f"source-bound dispatch guard {guard} rejects selected reservation")


if __name__ == "__main__":
    unittest.main()
