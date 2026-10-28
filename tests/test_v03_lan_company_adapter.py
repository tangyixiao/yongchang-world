"""Register the approved company-public arc with LAN's existing coordinator."""
import copy
import json
from pathlib import Path
import unittest

from tools.v03_inline_delivery_adapter import validate_inline_catalog, render_inline_country_adapters

ROOT = Path(__file__).resolve().parents[1]
SLUG = "v03_lan_company_public"


def catalog():
    return json.loads((ROOT / "data/content/v03/countries/lan.json").read_text(encoding="utf-8"))


class LanCompanyAdapter(unittest.TestCase):
    def test_major_cooldown_without_exact_new_receipt_cannot_ack_public_native_body(self):
        from shu_kor_strict_review_runtime import field
        from test_v03_lan_company_public import new_world, public_arc, option_legal
        world = new_world()
        arc = public_arc(world.cat)
        world.pulse(arc)
        self.assertEqual([event for _, event in world.events], ["ywc_lan.1100"])
        event = world.event_defs["ywc_lan.1100"]
        state = world.countries[world.tag]
        self.assertEqual(state["ywc_v03_lan_inline_reservation"], 37)
        valid = copy.deepcopy(world)
        fault = copy.deepcopy(field(event, "immediate"))
        changes = []
        def corrupt_receipt(nodes):
            for key, _, value in nodes:
                if key == "set_variable" and isinstance(value, list):
                    if field(value, "name") == "ywc_v03_lan_v03_lan_company_public_last_event":
                        for i, child in enumerate(value):
                            if child[0] == "value":
                                value[i] = ("value", "=", "0")
                                changes.append(1)
                if isinstance(value, list):
                    corrupt_receipt(value)
        corrupt_receipt(fault)
        self.assertEqual(len(changes), 1, "fault touches only the native receipt operand")
        world.execute(fault, world.tag)
        self.assertIn("ywc_v03_major_event_cooldown", state)
        self.assertEqual(state["ywc_v03_lan_v03_lan_company_public_last_event"], 0)
        self.assertEqual(state["ywc_v03_lan_inline_reservation"], 37)
        self.assertEqual(state["ywc_lan_public_pending_event"], 1100)
        self.assertFalse(option_legal(world, event, "term_company_republic"))
        world.execute([("ywc_v03_lan_inline_ack_37", "=", "yes")], world.tag)
        self.assertEqual(state["ywc_v03_lan_inline_reservation"], 37)
        self.assertEqual(state["ywc_lan_public_pending_event"], 1100)
        valid.execute(field(event, "immediate"), valid.tag)
        actual = valid.countries[valid.tag]
        self.assertEqual(actual["ywc_v03_lan_v03_lan_company_public_last_event"], 1)
        self.assertNotIn("ywc_v03_lan_inline_reservation", actual)
        self.assertNotIn("ywc_lan_public_pending_event", actual)
        self.assertTrue(option_legal(valid, event, "term_company_republic"))

    def test_public_and_two_old_arcs_share_actual_source_turns_and_ack_all_ten_new_events(self):
        from collections import Counter
        from shu_kor_strict_review_runtime import field
        from test_v03_lan_company_public import new_world, choose, option_legal
        current = catalog()
        participants = [current["arcs"][0], current["arcs"][2], current["arcs"][3]]
        candidate_map = {}
        ident = 0
        for arc in current["arcs"]:
            for proof in arc["inline_delivery_adapter"]["branches"]:
                for candidate in proof["candidates"]:
                    ident += 1
                    candidate_map[ident] = (arc["slug"], proof["event"], candidate["queue"])
        choices = {
            1100: "term_company_republic", 1101: "pay_charter", 1102: "verify_constituency",
            1103: "sign_bounded_mandate", 1104: "write_public_appeal",
            1105: "confirm_current_tax_base", 1106: "pay_public_review",
            1107: "accept_six_reviews", 1108: "confirm_current_mandate", 1109: "close_established",
        }
        for order in (participants, list(reversed(participants))):
            with self.subTest(order=[a["slug"] for a in order]):
                world = new_world(legacy=True)
                state = world.countries[world.tag]
                for arc in order:
                    world.refresh(arc)
                self.assertEqual((state["ywc_v03_active_arc_count"],
                                  state["ywc_v03_visible_task_count"]), (3, 3))
                deliveries = []
                for _ in range(120):
                    world.advance_months(1)
                    world.elapsed_months += 1
                    for arc in order:
                        for journal in arc["journals"]:
                            jid = journal["id"]
                            if jid not in world.active[world.tag]:
                                continue
                            body = world.journal_defs[jid]
                            world.execute(field(field(body, "on_monthly_pulse"), "effect"), world.tag)
                            while world.events:
                                _, event_id = world.events.pop(0)
                                ident = int(state["ywc_v03_lan_inline_reservation"])
                                self.assertEqual(candidate_map[ident][:2], (arc["slug"], event_id))
                                queue = candidate_map[ident][2]
                                other_queues = {name: value for name, value in state.items()
                                                if name.startswith("ywc_lan_")
                                                and name.endswith(("_pending_event", "_notice_event"))
                                                and name != queue}
                                event = world.event_defs[event_id]
                                self.assertTrue(world.conditions(field(event, "trigger"), world.tag))
                                world.execute(field(event, "immediate"), world.tag)
                                self.assertNotIn("ywc_v03_lan_inline_reservation", state)
                                self.assertNotIn("ywc_v03_lan_inline_timer", state)
                                self.assertNotIn(queue, state)
                                self.assertEqual({name: state[name] for name in other_queues}, other_queues)
                                slot = next(i for i, a in enumerate(current["arcs"], 1)
                                            if a["slug"] == arc["slug"])
                                self.assertEqual(state[f"ywc_v03_lan_inline_served_{slot}"],
                                                 state["ywc_v03_lan_inline_round"])
                                deliveries.append((arc["slug"], world.elapsed_months * 30, event_id, ident))
                                key = choices[int(event_id.split(".")[1])] if arc["slug"] == SLUG else "defer"
                                self.assertTrue(option_legal(world, event, key), (event_id, key))
                                choose(world, arc, event, key)
                        world.refresh(arc)
                self.assertEqual(Counter(row[0] for row in deliveries[:9]),
                                 Counter({a["slug"]: 3 for a in participants}))
                self.assertTrue(all(b[1] - a[1] >= 90 for a, b in zip(deliveries, deliveries[1:])))
                public = [row for row in deliveries if row[0] == SLUG]
                self.assertEqual([row[2] for row in public], [f"ywc_lan.{n}" for n in range(1100, 1110)])
                self.assertEqual([row[3] for row in public], list(range(37, 47)))
                self.assertEqual(state["ywc_lan_public_outcome"], 1)
                self.assertEqual((state["ywc_v03_active_arc_count"],
                                  state["ywc_v03_visible_task_count"]), (2, 2))

    def test_public_queue_extension_is_narrow_and_keeps_one_exact_candidate(self):
        from tools.v03_inline_delivery_adapter import _lan_source_binding
        def script(queue="ywc_lan_public_pending_event", op="=", value=1100):
            return ("{ on_monthly_pulse = { effect = { if = { limit = { "
                    f"ywc_lan_public_stage_1100 = yes var:{queue} {op} {value} "
                    f"}} remove_variable = {queue} trigger_event = {{ id = ywc_lan.1100 }} "
                    "} } } }")
        row = _lan_source_binding("ywc_je_v03_lan_public_mandate", script())["branches"][0]
        self.assertEqual(row["candidates"], [{"queue": "ywc_lan_public_pending_event",
                                              "kind": "normal", "mode": "exact", "value": 1100}])
        for queue, op, value in (
            ("ywc_lan_public_notice_event", "=", 12),
            ("ywc_lan_unregistered_pending_event", "=", 1100),
            ("ywc_shu_prov_pending_event", "=", 1100),
            ("ywc_lan_public_stage", "=", 1100),
            ("ywc_lan_public_pending_event", "?=", 1100),
            ("ywc_lan_public_pending_event", "=", 1101),
        ):
            with self.subTest(queue=queue, op=op, value=value), self.assertRaises(ValueError):
                _lan_source_binding("ywc_je_v03_lan_public_mandate", script(queue, op, value))

    def test_new_receipt_abi_is_exact_and_does_not_relax_old_immediates(self):
        from tools import v03_inline_delivery_adapter as adapter
        self.assertTrue(hasattr(adapter, "_lan_native_receipt"),
                        "explicit LAN native body/receipt validation is not implemented")
        native_receipt = adapter._lan_native_receipt
        old = {"id": "ywc_lan.1000", "immediate": "{ ywc_v03_mark_major_delivered = yes }"}
        self.assertEqual(native_receipt(old), (None, None))
        for number in range(1100, 1110):
            event = {"id": f"ywc_lan.{number}", "immediate":
                     "{ ywc_v03_mark_major_delivered = yes set_variable = { "
                     f"name = ywc_v03_lan_v03_lan_company_public_last_event value = {number - 1099} "
                     "} }"}
            self.assertEqual(native_receipt(event), ("ywc_v03_lan_v03_lan_company_public_last_event", number - 1099))
            for wrong in (
                event["immediate"].replace("ywc_v03_lan_v03_lan_company_public_last_event", "ywc_lan_mine_last_event"),
                event["immediate"].replace(f"value = {number - 1099}", "value = 0"),
                event["immediate"].replace("set_variable", "change_variable"),
                event["immediate"].replace("= yes", "= no"),
                event["immediate"][:-1] + "add_treasury = 100 }",
            ):
                with self.subTest(number=number, wrong=wrong), self.assertRaises(ValueError):
                    native_receipt({**event, "immediate": wrong})
        for wrong in (
            old["immediate"][:-1] + "set_variable = { name = ywc_v03_lan_v03_lan_company_public_last_event value = 1 } }",
            "{ ywc_v03_mark_major_delivered = no }",
        ):
            with self.assertRaises(ValueError):
                native_receipt({**old, "immediate": wrong})
        with self.assertRaises(ValueError):
            native_receipt({"id": "ywc_lan.1110", "immediate": old["immediate"]})

    def test_unregistered_extension_is_rejected_with_or_without_metadata(self):
        for metadata in (False, True):
            with self.subTest(metadata=metadata):
                current = catalog()
                extra = copy.deepcopy(current["arcs"][0])
                extra.update(slug="v03_lan_unregistered_extension", era="middle")
                if not metadata:
                    extra.pop("inline_delivery_adapter")
                current["arcs"].append(extra)
                with self.assertRaisesRegex(ValueError, "unregistered LAN inline arc"):
                    validate_inline_catalog(current)

    def test_renderer_cannot_leave_unknown_middle_as_an_uncoordinated_source(self):
        current = catalog()
        extra = copy.deepcopy(current["arcs"][0])
        extra.update(slug="v03_lan_unregistered_extension", era="middle")
        current["arcs"].append(extra)
        with self.assertRaisesRegex(ValueError, "unregistered LAN inline arc"):
            render_inline_country_adapters(current)

    def test_approved_company_card_has_ten_events_three_phases_and_fourth_slot(self):
        current = catalog()
        matches = [arc for arc in current["arcs"] if arc["slug"] == SLUG]
        self.assertEqual(len(matches), 1, "the approved company-public card is not implemented")
        arc = matches[0]
        self.assertEqual(arc["era"], "middle")
        self.assertEqual({e["id"] for e in arc["events"]},
                         {f"ywc_lan.{number}" for number in range(1100, 1110)})
        self.assertEqual(len(arc["journals"]), 3)
        old = [a for a in current["arcs"] if a["era"] == "foundation"]
        self.assertEqual(sum(len(a["inline_delivery_adapter"]["branches"]) for a in old), 36)
        self.assertEqual(len(arc["inline_delivery_adapter"]["branches"]), 10)
        validate_inline_catalog(current)
        generated = render_inline_country_adapters(current)
        self.assertIn("ywc_v03_lan_inline_served_4", generated["effects"])
        for ident in range(37, 47):
            self.assertIn(f"ywc_v03_lan_inline_candidate_{ident} =", generated["triggers"])


if __name__ == "__main__":
    unittest.main()
