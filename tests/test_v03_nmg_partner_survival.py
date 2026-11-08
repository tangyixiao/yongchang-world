"""Selected NMG options survive partner loss in the strict source subset.

The observer rejects an actual relation leaf with an absent country target;
this is an observability boundary, not a claim about Clausewitz engine errors.
"""
import copy
import unittest

from tests.test_v03_nmg_foundation_lifecycle import (
    CATALOG, NmgWorld, event_option, field, fixture, parse,
)


CASES = (
    ("ywc_nmg.1024", "escalate", -10),
    ("ywc_nmg.1026", "walk_out", -25),
    ("ywc_nmg.1028", "own_arrears", -5),
    ("ywc_nmg.1028", "dispute", -25),
    ("ywc_nmg.1029", "withdraw", -25),
)
REVENUE = "ywc_nmg_revenue_"
ADMISSION = "ywc_v03_nmg_v03_nmg_autonomy_revenue_"


class PartnerObservingWorld(NmgWorld):
    def __init__(self, countries):
        super().__init__(countries)
        self.relation_operations = []
        self.slot_releases = 0

    def execute(self, nodes, tag):
        for key, _, body in nodes:
            if key == "change_relations":
                target = field(body, "country").removeprefix("c:")
                amount = float(field(field(body, "value"), "add"))
                self.relation_operations.append((tag, target, amount))
                if target not in self.countries:
                    raise AssertionError(("absent_relation_target", tag, target, amount))
            elif key == "ywc_nmg_release_slot":
                self.slot_releases += 1
        return super().execute(nodes, tag)


def selected_popup(notice, arrears=False, event_id=None):
    """A deterministic effect boundary after delivery consumed the normal queue.

    Independent NMG is settling a paid old obligation in both controls. An
    active notice retains its genuine pending/return1025; the selected option
    itself owns any subsequent queue overwrite or response cleanup.
    """
    countries = fixture()
    countries["NMG"].update({
        "fixture_subject": 0, "fixture_mex_overlord": 0,
        "ywc_v03_active_arc_count": 1, "ywc_v03_visible_task_count": 1,
        ADMISSION + "started": 1, ADMISSION + "outcome": 0,
        REVENUE + "opened": 1, REVENUE + "stage3": 1,
        REVENUE + "route": 3 if arrears else 1,
        REVENUE + "quota_paid": 1, REVENUE + "quota": 1000,
        REVENUE + "blocked_defer": 1,
    })
    if event_id == "ywc_nmg.1026":
        # Walk-out is selected from the negotiation JE, before settlement.
        countries["NMG"].pop(REVENUE + "stage3")
        countries["NMG"][REVENUE + "stage2"] = 1
    if arrears:
        countries["NMG"][REVENUE + "arrears"] = 1
    if notice:
        countries["NMG"].update({
            REVENUE + "pending": 1025,
            REVENUE + "notice_response_context": 1,
            REVENUE + "notice_return_event": 1025,
        })
    world = PartnerObservingWorld(countries)
    world.treasury["NMG"] = -1000  # The old quota was paid before this popup.
    return world


def selected_option(event_id, key, representation):
    if representation == "source":
        option = next(option for arc in CATALOG["arcs"] for event in arc["events"]
                      if event["id"] == event_id for option in event["options"]
                      if option["key"] == key)
        return parse(option["trigger"].strip()[1:-1]), parse(option["effect"].strip()[1:-1])
    option = event_option(event_id, key)
    for name, _, body in option:
        if name == "custom_tooltip":
            text_only = (isinstance(body, list) and len(body) == 1
                         and body[0][:2] == ("text", "=") and isinstance(body[0][2], str))
            if not isinstance(body, str) and not text_only:
                raise AssertionError(("tooltip_must_not_hide_effects", body))
    return field(option, "trigger"), [node for node in option
                                     if node[0] not in ("name", "trigger", "ai_chance", "custom_tooltip")]


def comparable_local_state(world):
    state = copy.deepcopy(vars(world))
    state["countries"].pop("MEX", None)
    state["countries"]["NMG"].pop("fixture_relations")
    state.pop("relation_operations")
    return state


class NmgPartnerSurvivalTest(unittest.TestCase):
    def assert_local_progress(self, world, key, notice, arrears=False):
        v = world.countries["NMG"]
        self.assertEqual(v["fixture_subject"], 0)
        self.assertEqual(v["fixture_mex_overlord"], 0)
        self.assertEqual(v[REVENUE + "route"], 3 if arrears else 1)
        self.assertEqual(v[REVENUE + "quota_paid"], 1)
        self.assertEqual(v[REVENUE + "quota"], 1000)
        self.assertEqual(world.treasury["NMG"], -1000)
        if key == "withdraw":
            self.assertEqual(v[ADMISSION + "settled"], 1)
            self.assertEqual(v[ADMISSION + "outcome"], 1)  # Existing failure outcome.
            self.assertEqual(v[REVENUE + "withdrawn"], 1)
            self.assertEqual(v[REVENUE + "closed"], 1)
            self.assertNotIn(REVENUE + "established", v)
            self.assertNotIn(REVENUE + "compromise", v)
            self.assertEqual(v["ywc_v03_active_arc_count"], 0)
            self.assertEqual(v["ywc_v03_visible_task_count"], 0)
            self.assertEqual(world.slot_releases, 1)
            # The closer is idempotent; another close cannot release a second slot.
            world.run("ywc_nmg_close_revenue_as_breach", "NMG")
            self.assertEqual(world.slot_releases, 1)
            self.assertEqual(v["ywc_v03_active_arc_count"], 0)
            self.assertEqual(v["ywc_v03_visible_task_count"], 0)
            if notice:
                self.assertEqual(v[REVENUE + "pending"], 1025)
            else:
                self.assertNotIn(REVENUE + "pending", v)
        else:
            marker, pending = {
                "escalate": ("escalated", 1025),
                "walk_out": ("blocked_defer", 1023),
                "own_arrears": ("arrears_owned", 1025 if notice else 1029),
                "dispute": ("disputed", 1025 if notice else 1029),
            }[key]
            self.assertEqual(v[REVENUE + marker], 1)
            self.assertEqual(v[REVENUE + "pending"], pending)
            self.assertNotIn(ADMISSION + "settled", v)
            self.assertEqual(v[ADMISSION + "outcome"], 0)
            self.assertEqual(v["ywc_v03_active_arc_count"], 1)
            self.assertEqual(v["ywc_v03_visible_task_count"], 1)
            self.assertEqual(world.slot_releases, 0)
        if key != "walk_out":
            self.assertNotIn(REVENUE + "blocked_defer", v)
        # Only these selected source options contain notice response cleanup.
        for suffix in ("notice_response_context", "notice_return_event"):
            if notice and key in ("escalate", "walk_out"):
                self.assertEqual(v[REVENUE + suffix], 1 if suffix.endswith("context") else 1025)
            else:
                self.assertNotIn(REVENUE + suffix, v)

    def test_selected_option_survives_mex_disappearing_before_effect(self):
        for event_id, key, _ in CASES:
            for representation in ("source", "generated"):
                for notice in (False, True):
                    with self.subTest(option=f"{event_id}.{key}", representation=representation,
                                      context="notice" if notice else "normal"):
                        present = selected_popup(notice, event_id=event_id)
                        absent = selected_popup(notice, event_id=event_id)
                        trigger, effect = selected_option(event_id, key, representation)
                        self.assertIn("MEX", absent.countries)
                        self.assertTrue(present.conditions(trigger, "NMG"))
                        self.assertTrue(absent.conditions(trigger, "NMG"))
                        del absent.countries["MEX"]  # Selection predates partner loss.
                        present.execute(effect, "NMG")
                        absent.execute(effect, "NMG")
                        self.assertEqual(absent.relation_operations, [])
                        self.assertEqual(absent.countries["NMG"]["fixture_relations"], 50)
                        self.assert_local_progress(present, key, notice)
                        self.assert_local_progress(absent, key, notice)
                        self.assertEqual(comparable_local_state(absent), comparable_local_state(present))

    def test_present_mex_preserves_original_costs_and_conditional_withdrawal(self):
        # Twenty ordinary controls plus four route3/arrears controls: the native
        # closer charges -25 once there, with no additional generic caller hit.
        controls = [(event_id, key, cost, False) for event_id, key, cost in CASES]
        controls.append(("ywc_nmg.1029", "withdraw", -25, True))
        for event_id, key, cost, arrears in controls:
            for representation in ("source", "generated"):
                for notice in (False, True):
                    with self.subTest(option=f"{event_id}.{key}", representation=representation,
                                      context="notice" if notice else "normal", arrears=arrears):
                        world = selected_popup(notice, arrears, event_id=event_id)
                        trigger, effect = selected_option(event_id, key, representation)
                        self.assertTrue(world.conditions(trigger, "NMG"))
                        world.execute(effect, "NMG")
                        self.assert_local_progress(world, key, notice, arrears)
                        self.assertEqual(world.relation_operations, [("NMG", "MEX", cost)])
                        self.assertEqual(world.countries["NMG"]["fixture_relations"], 50 + cost)
                        self.assertEqual(world.countries["MEX"], {"fixture_relations": 50})
                        self.assertEqual(world.treasury["MEX"], 0)


if __name__ == "__main__":
    unittest.main()
