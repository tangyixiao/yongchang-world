"""Aggregate recipient fairness contract over the authored OIR source runner.

This test deliberately exercises real admissions, live JE pulses, actual dispatch
triggers/immediates, legal defer options and the shared 90-day timer. No route,
fee, pending queue, or scheduler bookkeeping is pre-seeded by the fixture.
"""
import itertools
import json
import re
import copy
import unittest
from pathlib import Path

from tests.test_v03_oir_foundation import world, start, pulse_current, fire, choose
from tools.build_v03_content import _render_journal_file
from tools.v03_delivery_scheduler import (
    validate_catalogue_adapters, render_country_adapters, choose_next_dispatch,
)

ROOT = Path(__file__).resolve().parents[1]
COUNTRIES = ("dmg", "jhg", "kor", "lan", "mgl", "nmg", "nqg", "oir", "shu", "tib")


class AggregateSchedulerContract(unittest.TestCase):
    def test_comparison_parser_supports_only_var_greater_than_scalar_or_var(self):
        definitions={}
        expr=parse_script("probe = { var:left > 3 }")["probe"]
        self.assertFalse(eval_expr(expr,{"left":2},definitions))
        self.assertFalse(eval_expr(expr,{"left":3},definitions))
        self.assertTrue(eval_expr(expr,{"left":4},definitions))
        var_expr=parse_script("probe = { var:left > var:right }")["probe"]
        self.assertTrue(eval_expr(var_expr,{"left":4,"right":3},definitions))
        with self.assertRaises(AssertionError): parse_script("probe = { has_variable > 1 }")
        malformed=parse_script("probe = { var:left > no }")
        with self.assertRaisesRegex(AssertionError,"invalid > comparison shape"):
            eval_expr(malformed["probe"],{},definitions)
        parsed=parse_script("probe = { var:left > var:right AND = { unknown = yes } }")
        with self.assertRaisesRegex(AssertionError,"unknown predicate"):
            eval_expr(parsed["probe"],{},definitions)

    def test_ten_catalogues_declare_three_arcs_with_je_and_events(self):
        total = 0
        for tag in COUNTRIES:
            catalog = json.loads((ROOT / "data/content/v03/countries" / f"{tag}.json").read_text(encoding="utf-8-sig"))
            foundation = [a for a in catalog["arcs"] if a.get("era") == "foundation"]
            self.assertEqual(len(foundation), 3, tag)
            total += len(foundation)
            for arc in foundation:
                self.assertTrue(arc["journals"], (tag, arc["slug"]))
                self.assertTrue(arc["events"], (tag, arc["slug"]))
                self.assertEqual(len({j["id"] for j in arc["journals"]}), len(arc["journals"]))
                self.assertEqual(len({e["id"] for e in arc["events"]}), len(arc["events"]))
        self.assertEqual(total, 30)

    def test_real_oir_scheduler_is_fair_for_all_pulse_orders(self):
        catalog = json.loads((ROOT / "data/content/v03/countries/oir.json").read_text(encoding="utf-8-sig"))
        arcs = catalog["arcs"]
        for order in itertools.permutations(arcs):
            with self.subTest(order=tuple(a["slug"] for a in order)):
                w = world()
                for arc in arcs:
                    start(w, arc)
                self.assertEqual(w.countries["OIR"]["ywc_v03_active_arc_count"], 3)
                counts = {arc["slug"]: 0 for arc in arcs}
                event_to_arc = {event["id"]: arc for arc in arcs for event in arc["events"]}
                for round_index in range(15):
                    if round_index:
                        w.advance_days(90)
                    for driver in order:
                        before = len(w.events)
                        pulse_current(w, driver)
                        if len(w.events) == before:
                            continue
                        tag, event_id = w.events[-1]
                        self.assertEqual(tag, "OIR")
                        recipient = event_to_arc[event_id]
                        ev = fire(w, recipient, int(event_id.rsplit(".", 1)[1]))
                        choose(w, ev, "defer")
                        counts[recipient["slug"]] += 1
                self.assertEqual(sum(counts.values()), 15)
                self.assertEqual(counts, {arc["slug"]: 5 for arc in arcs}, counts)


    def test_metadata_renders_exact_arc_phase_and_queue_adapter(self):
        catalog = fixture_catalog()
        validate_catalogue_adapters(catalog)
        rendered = render_country_adapters(catalog)
        triggers = rendered["triggers"]
        effects = rendered["effects"]
        self.assertIn("ywc_v03_scheduler_candidate_alpha_normal_pending = {", triggers)
        self.assertIn("has_variable = alpha_started", triggers)
        self.assertIn("NOT = { has_variable = alpha_settled }", triggers)
        self.assertIn("var:alpha_pending = 1", triggers)
        self.assertIn("var:alpha_notice = 1", triggers)
        self.assertIn("ywc_v03_alpha_live = yes", triggers)
        self.assertNotIn("ywc_v03_can_deliver_major", triggers)
        self.assertIn("ywc_v03_scheduler_turn_alpha = {", triggers)
        self.assertIn("ywc_v03_scheduler_ack_alpha_normal_pending", effects)
        self.assertIn("ywc_v03_scheduler_ack_alpha_notice12_pending", effects)
        self.assertIn("set_variable = { name = ywc_v03_demo_reservation_timer value = 1 days = 1 }", effects)

    def test_existing_on_complete_is_extended_without_adding_a_duplicate(self):
        catalog = fixture_catalog()
        for arc in catalog["arcs"]:
            slug = arc["slug"]
            arc["delivery_adapter"]["live_phases"][0]["live_witness"] = f"{slug}_live"
            journal = arc["journals"][0]
            journal["goal"] = "{ has_variable = done }"
            journal["exit_conditions"] = "{ has_variable = failed }"
            completion = " on_complete = { set_variable = { name = existing_cleanup value = 1 } }" if slug == "alpha" else ""
            journal["script"] = (
                "{ immediate = { set_variable = { name = " + f"{slug}_started" + " value = 1 } }"
                " on_fail = { remove_variable = " + f"{slug}_started" + " }"
                + completion
                + " on_monthly_pulse = { effect = { "
                + f"ywc_demo_dispatch_{slug}"
                + " = yes } } }"
            )
        adapter = render_country_adapters(catalog)
        rendered = _render_journal_file(catalog, adapter)
        ast = parse_script("\n".join(line for line in rendered.splitlines() if not line.startswith("#")))
        alpha = ast["ywc_je_demo_alpha"]
        blocks = [value for key, value in alpha if key == "on_complete"]
        self.assertEqual(len(blocks), 1)
        self.assertIn("existing_cleanup", repr(blocks[0]))
        self.assertIn("remove_variable", repr(blocks[0]))
        self.assertIn("alpha_live", repr(blocks[0]))

    def test_fair_turns_are_order_independent_and_keep_due_remedies_first(self):
        import itertools
        slugs = ("alpha", "beta", "gamma")
        expected = {"alpha": 5, "beta": 5, "gamma": 5}
        for order in itertools.permutations(slugs):
            round_number = 1
            served = {slug: 0 for slug in slugs}
            delivered = {slug: 0 for slug in slugs}
            for _ in range(15):
                round_number, slug, candidate = choose_next_dispatch(
                    order, round_number, served,
                    {s: [{"kind": "normal", "event_id": s + ".normal"}] for s in slugs},
                )
                self.assertEqual(candidate["kind"], "normal")
                served[slug] = round_number
                delivered[slug] += 1
            self.assertEqual(delivered, expected)

        order = ("alpha", "beta", "gamma")
        _, slug, candidate = choose_next_dispatch(
            order, 1, {s: 0 for s in order},
            {"alpha": [{"kind": "normal", "event_id": "a"}],
             "beta": [{"kind": "notice36", "event_id": "b36"}],
             "gamma": [{"kind": "notice12", "event_id": "c12"}]},
        )
        self.assertEqual((slug, candidate["event_id"]), ("gamma", "c12"))

    def test_shared_event_and_flag_queues_keep_distinct_candidate_identity(self):
        catalog = fixture_catalog()
        arc = catalog["arcs"][0]
        # NQG-style flags share one event; acknowledgement is tied to the exact flag.
        event_id = arc["events"][1]["id"]
        normal_id = arc["events"][0]["id"]
        arc["delivery_adapter"]["queues"] = [
            {"kind": "normal", "variable": "winter_pending", "candidates": [
                {"key": "winter_normal", "event_id": normal_id, "value": 1, "guard": "{ has_variable = winter_open }"}]},
            {"kind": "notice12", "variable": "notice12_pending", "candidates": [
                {"key": "notice12", "event_id": event_id, "value": 1, "guard": "{ has_variable = notice12_intent }",
                 "acknowledgement": [{"op": "remove", "variable": "notice12_intent"}]}]},
            {"kind": "notice36", "variable": "notice36_pending", "candidates": [
                {"key": "notice36", "event_id": event_id, "value": 1, "guard": "{ has_variable = notice36_intent }",
                 "acknowledgement": [{"op": "remove", "variable": "notice36_intent"}] } ]},
        ]
        rendered = render_country_adapters(catalog)
        self.assertIn("ywc_v03_scheduler_ack_alpha_notice12", rendered["effects"])
        self.assertIn("ywc_v03_scheduler_ack_alpha_notice36", rendered["effects"])
        self.assertIn("ywc_v03_scheduler_ack_alpha_winter_normal", rendered["effects"])
        self.assertNotEqual("ywc_v03_scheduler_ack_alpha_notice12", "ywc_v03_scheduler_ack_alpha_winter_normal")
        notice_ack = rendered["effects"].split("ywc_v03_scheduler_ack_alpha_notice12 = {",1)[1].split("\n}",1)[0]
        normal_ack = rendered["effects"].split("ywc_v03_scheduler_ack_alpha_winter_normal = {",1)[1].split("\n}",1)[0]
        self.assertIn("remove_variable = notice12_pending", notice_ack)
        self.assertIn("remove_variable = winter_pending", normal_ack)
        self.assertNotIn("remove_variable = winter_pending", notice_ack)
        self.assertNotIn("remove_variable = notice12_pending", normal_ack)

    def test_strict_metadata_and_dynamic_class_priority(self):
        catalog=fixture_catalog()
        # Future-era arcs are not silently treated as foundation adapters.
        future=dict(catalog["arcs"][0]); future["slug"]="future_arc"; future["era"]="resilience"
        catalog["arcs"].append(future)
        validate_catalogue_adapters(catalog)
        bad=fixture_catalog(); bad["arcs"][0]["events"].append(dict(bad["arcs"][0]["events"][0]))
        with self.assertRaisesRegex(ValueError,"duplicate IDs"):
            validate_catalogue_adapters(bad)
        bad=fixture_catalog(); bad["arcs"][0]["delivery_adapter"]["queues"][0]["candidates"][0]["value"]=True
        with self.assertRaisesRegex(ValueError,"nonnegative integer"):
            validate_catalogue_adapters(bad)
        bad=fixture_catalog(); bad["arcs"][0]["delivery_adapter"]["unexpected"]=1
        with self.assertRaisesRegex(ValueError,"unknown"):
            validate_catalogue_adapters(bad)
        order=("alpha","beta","gamma")
        # Beta's declared notice queue is absent from the current candidates, so it cannot block alpha.
        _,slug,candidate=choose_next_dispatch(order,1,{s:0 for s in order},
            {"alpha":[{"kind":"normal","event_id":"a"}],"beta":[{"kind":"normal","event_id":"b"}],"gamma":[{"kind":"normal","event_id":"c"}]})
        self.assertEqual((slug,candidate["event_id"]),("alpha","a"))
        # Candidate input insertion order does not alter the fixed tie order.
        eligible={"gamma":[{"kind":"normal","event_id":"c"}],"alpha":[{"kind":"normal","event_id":"a"}],"beta":[{"kind":"notice12","event_id":"b12"}]}
        _,slug,candidate=choose_next_dispatch(order,1,{s:0 for s in order},eligible)
        self.assertEqual((slug,candidate["event_id"]),("beta","b12"))

    def test_scheduler_variable_roles_and_receipt_presence_are_strict(self):
        # A queue may be reused by multiple candidate kinds in one arc, but it
        # cannot alias ownership or phase witnesses, including across arcs.
        valid = fixture_catalog()
        first = valid["arcs"][0]["delivery_adapter"]
        first["queues"][1]["variable"] = first["queues"][0]["variable"]
        first["queues"][1]["kind"] = "notice12"
        validate_catalogue_adapters(valid)

        mutations = (
            lambda c: c["arcs"][0]["delivery_adapter"]["queues"][0].__setitem__("variable", c["arcs"][0]["delivery_adapter"]["owner_started"]),
            lambda c: c["arcs"][0]["delivery_adapter"]["live_phases"][0].__setitem__("live_witness", c["arcs"][0]["delivery_adapter"]["owner_settled"]),
            lambda c: c["arcs"][0]["delivery_adapter"]["live_phases"][0].__setitem__("live_witness", c["arcs"][0]["delivery_adapter"]["queues"][0]["variable"]),
            lambda c: c["arcs"][1]["delivery_adapter"]["queues"][0].__setitem__("variable", c["arcs"][0]["delivery_adapter"]["live_phases"][0].get("live_witness", "alpha_witness")),
        )
        for mutate in mutations:
            bad = fixture_catalog()
            bad["arcs"][0]["delivery_adapter"]["live_phases"][0]["live_witness"] = "alpha_witness"
            mutate(bad)
            with self.assertRaisesRegex(ValueError, "aliases another role or arc|aliases another role"):
                validate_catalogue_adapters(bad)

        bad = fixture_catalog()
        bad["delivery_adapter"] = None
        with self.assertRaisesRegex(ValueError, "unknown"):
            validate_catalogue_adapters(bad)

        for pair in (("receipt_variable", None), ("receipt_value", 0)):
            bad = fixture_catalog()
            candidate = bad["arcs"][0]["delivery_adapter"]["queues"][0]["candidates"][0]
            candidate[pair[0]] = pair[1]
            with self.assertRaisesRegex(ValueError, "receipt variable/value|script identifier"):
                validate_catalogue_adapters(bad)
        bad = fixture_catalog()
        candidate = bad["arcs"][0]["delivery_adapter"]["queues"][0]["candidates"][0]
        candidate["receipt_variable"] = "alpha_started"
        candidate["receipt_value"] = 1
        with self.assertRaisesRegex(ValueError, "receipt variable aliases another role"):
            validate_catalogue_adapters(bad)
        bad = fixture_catalog()
        bad["arcs"][0]["delivery_adapter"]["queues"][0]["variable"] = "ywc_v03_demo_delivery_round"
        with self.assertRaisesRegex(ValueError, "queue variable aliases another role or arc"):
            validate_catalogue_adapters(bad)
        bad = fixture_catalog()
        candidate = bad["arcs"][0]["delivery_adapter"]["queues"][0]["candidates"][0]
        candidate["receipt_variable"] = None
        candidate["receipt_value"] = None
        with self.assertRaisesRegex(ValueError, "script identifier"):
            validate_catalogue_adapters(bad)
        bad = fixture_catalog()
        bad["arcs"][0]["delivery_adapter"]["live_phases"][0]["live_witness"] = "shared_witness"
        bad["arcs"][0]["journals"].append({"id": "ywc_je_demo_alpha_second"})
        bad["arcs"][0]["delivery_adapter"]["live_phases"].append(
            {"journal": "ywc_je_demo_alpha_second", "predicate": "{ ywc_v03_alpha_live = yes }", "live_witness": "shared_witness"})
        with self.assertRaisesRegex(ValueError, "aliases another role"):
            validate_catalogue_adapters(bad)

        catalog = fixture_catalog()
        candidate = catalog["arcs"][0]["delivery_adapter"]["queues"][0]["candidates"][0]
        candidate["receipt_variable"] = "alpha_receipt"
        candidate["receipt_value"] = 0
        rendered = render_country_adapters(catalog)
        effects = parse_script(rendered["effects"])
        ack_name = "ywc_v03_scheduler_ack_alpha_normal_pending"
        missing = {"alpha_started": 1, "alpha_pending": 1, "alpha_ready": 1,
                   "ywc_v03_alpha_live": 1, "ywc_v03_demo_delivery_round": 1}
        run_effect(effects["ywc_v03_scheduler_reserve_alpha_normal_pending"], missing, parse_script(rendered["triggers"]))
        run_effect(effects[ack_name], missing, parse_script(rendered["triggers"]))
        self.assertEqual(missing["alpha_pending"], 1)
        self.assertNotIn("ywc_v03_scheduler_served_alpha", missing)
        present_zero = dict(missing, alpha_receipt=0)  # Toy native receipt fact for presence-vs-missing only.
        _run_inline_proof(rendered, "ywc_demo.1000", present_zero, parse_script(rendered["triggers"]))
        run_effect(effects[ack_name], present_zero, parse_script(rendered["triggers"]))
        self.assertNotIn("alpha_pending", present_zero)
        self.assertIn("ywc_v03_scheduler_served_alpha", present_zero)

    def test_generated_turn_ast_ack_defer_and_next_recipient(self):
        catalog=fixture_catalog(); rendered=render_country_adapters(catalog)
        triggers=parse_script(rendered["triggers"]); effects=parse_script(rendered["effects"])
        state={"alpha_started":1,"beta_started":1,"gamma_started":1,
               "alpha_pending":1,"alpha_notice":1,"beta_pending":1,"gamma_pending":1,
               "ywc_v03_demo_delivery_round":1,
               "ywc_v03_alpha_live":1,"ywc_v03_beta_live":1,"ywc_v03_gamma_live":1,"alpha_ready":1,"beta_ready":1,"gamma_ready":1}
        # Real generated turn branch chooses alpha's notice, not its normal queue.
        self.assertTrue(eval_script(triggers, "ywc_v03_scheduler_turn_alpha_notice12_pending", state, triggers))
        self.assertFalse(eval_script(triggers, "ywc_v03_scheduler_turn_alpha_normal_pending", state, triggers))
        run_effect(effects["ywc_v03_scheduler_reserve_alpha_notice12_pending"], state, triggers)
        self.assertTrue(eval_script(triggers, "ywc_v03_scheduler_dispatch_alpha_notice12_pending", state, triggers))
        # Event immediate acknowledges the exact notice, then the option defers and
        # creates an ordinary pending queue. After the 90-day cooldown, beta is eligible.
        _run_inline_proof(rendered, "ywc_demo.1010", state, triggers)
        run_effect(effects["ywc_v03_scheduler_ack_alpha_notice12_pending"], state, triggers)
        self.assertEqual(state["alpha_ack_seen"],1)
        ack_text=rendered["effects"].split("ywc_v03_scheduler_ack_alpha_notice12_pending = {",1)[1].split("\n}",1)[0]
        self.assertLess(ack_text.index("alpha_ack_seen"),ack_text.index("remove_variable = alpha_notice"))
        state["alpha_pending"]=1
        state["ywc_v03_major_event_cooldown"]=1
        state["cooldown_days"]=90
        advance_test_days(state,89)
        run_effect(effects["ywc_v03_scheduler_prepare_demo"], state, triggers)
        self.assertFalse(eval_script(triggers, "ywc_v03_scheduler_turn_beta_normal_pending", state, triggers))
        advance_test_days(state,1); state.pop("ywc_v03_major_event_cooldown",None)
        run_effect(effects["ywc_v03_scheduler_prepare_demo"], state, triggers)
        self.assertFalse(eval_script(triggers, "ywc_v03_scheduler_turn_alpha_normal_pending", state, triggers))
        self.assertTrue(eval_script(triggers, "ywc_v03_scheduler_turn_beta_normal_pending", state, triggers))

    def test_generated_round_kernel_fair_five_each_for_all_orders(self):
        catalog=fixture_catalog()
        # Keep only one normal candidate per arc to exercise the complete rendered round kernel.
        for arc in catalog["arcs"]:
            arc["delivery_adapter"]["queues"]=[arc["delivery_adapter"]["queues"][0]]
            arc["events"]=[arc["events"][0]]
        rendered=render_country_adapters(catalog); triggers=parse_script(rendered["triggers"]); effects=parse_script(rendered["effects"])
        for order in itertools.permutations(("alpha","beta","gamma")):
            state={"alpha_started":1,"beta_started":1,"gamma_started":1,"ywc_v03_alpha_live":1,"ywc_v03_beta_live":1,"ywc_v03_gamma_live":1,
                   "alpha_pending":1,"beta_pending":1,"gamma_pending":1,"alpha_ready":1,"beta_ready":1,"gamma_ready":1,"ywc_v03_demo_delivery_round":1}
            counts={s:0 for s in order}
            for _ in range(15):
                run_effect(effects["ywc_v03_scheduler_prepare_demo"],state,triggers)
                choices=[s for s in order if eval_script(triggers,f"ywc_v03_scheduler_turn_{s}_normal_pending",state,triggers)]
                self.assertTrue(choices,state)
                slug=choices[0]; run_effect(effects[f"ywc_v03_scheduler_reserve_{slug}_normal_pending"],state,triggers)
                _run_inline_proof(rendered, f"ywc_demo.{1000 + (('alpha','beta','gamma').index(slug))}", state, triggers)
                run_effect(effects[f"ywc_v03_scheduler_ack_{slug}_normal_pending"],state,triggers)
                counts[slug]+=1
                # Legal defer/retry is an ordinary queue write after the immediate.
                state[f"{slug}_pending"]=1
                state.pop("ywc_v03_major_event_cooldown",None)
            self.assertEqual(counts,{"alpha":5,"beta":5,"gamma":5})

    def test_generated_candidate_authority_is_12_then_36_then_normal(self):
        catalog=fixture_catalog(); arc=catalog["arcs"][0]
        normal=arc["delivery_adapter"]["queues"][0]
        n12=arc["delivery_adapter"]["queues"][1]
        event36=arc["events"][1]["id"]
        arc["events"].append({"id":"ywc_demo.1099"})
        arc["delivery_adapter"]["queues"].append({"kind":"notice36","variable":"alpha_notice36","candidates":[
            {"key":"notice36_pending","event_id":"ywc_demo.1099","value":1,"guard":"{ has_variable = alpha_ready }"}]})
        rendered=render_country_adapters(catalog); triggers=parse_script(rendered["triggers"])
        state={"alpha_started":1,"ywc_v03_alpha_live":1,"alpha_ready":1,"alpha_pending":1,"alpha_notice":1,"alpha_notice36":1,
               "ywc_v03_demo_delivery_round":1}
        self.assertTrue(eval_script(triggers,"ywc_v03_scheduler_turn_alpha_notice12_pending",state,triggers))
        self.assertFalse(eval_script(triggers,"ywc_v03_scheduler_turn_alpha_notice36_pending",state,triggers))
        self.assertFalse(eval_script(triggers,"ywc_v03_scheduler_turn_alpha_normal_pending",state,triggers))
        self.assertFalse(eval_script(triggers,"ywc_v03_scheduler_dispatch_alpha_normal_pending",state,triggers))
        # Once alpha readiness is lost, it no longer blocks beta's due notice.
        state.pop("alpha_ready",None)
        state["beta_started"]=1; state["ywc_v03_beta_live"]=1
        state["beta_notice"]=1; state["beta_ready"]=1
        self.assertTrue(eval_script(triggers,"ywc_v03_scheduler_turn_beta_notice12_pending",state,triggers))

    def test_generated_reservation_expiry_phase_and_queue_replacement_fail_closed(self):
        catalog=fixture_catalog(); rendered=render_country_adapters(catalog)
        triggers=parse_script(rendered["triggers"]); effects=parse_script(rendered["effects"])
        base={"alpha_started":1,"ywc_v03_alpha_live":1,"alpha_ready":1,"alpha_pending":1,"ywc_v03_demo_delivery_round":1}
        # Presence is the Clausewitz contract even when a variable stores numeric zero.
        settled_zero={"alpha_started":1,"alpha_settled":0,"ywc_v03_alpha_live":1,"alpha_ready":1,"alpha_pending":1,"ywc_v03_demo_delivery_round":1}
        self.assertFalse(eval_script(triggers,"ywc_v03_scheduler_candidate_alpha_normal_pending",settled_zero,triggers))
        # Reserve one exact candidate, then lose its one-day timer: prepare clears it,
        # expired ACK cannot consume the queue or mark the recipient served.
        run_effect(effects["ywc_v03_scheduler_reserve_alpha_normal_pending"],base,triggers)
        advance_test_days(base,1)
        self.assertNotIn("ywc_v03_demo_reservation_timer",base)
        run_effect(effects["ywc_v03_scheduler_ack_alpha_normal_pending"],base,triggers)
        self.assertEqual(base["alpha_pending"],1)
        self.assertNotIn("ywc_v03_scheduler_served_alpha",base)
        run_effect(effects["ywc_v03_scheduler_prepare_demo"],base,triggers)
        run_effect(effects["ywc_v03_scheduler_ack_alpha_normal_pending"],base,triggers)
        self.assertEqual(base["alpha_pending"],1)
        self.assertNotIn("ywc_v03_scheduler_served_alpha",base)
        self.assertNotIn("ywc_v03_demo_reservation_arc",base)
        self.assertTrue(eval_script(triggers,"ywc_v03_scheduler_turn_alpha_normal_pending",base,triggers))
        # A live-phase loss and queue-value replacement invalidate the same reservation.
        for mutate in (lambda st: st.pop("ywc_v03_alpha_live",None), lambda st: st.__setitem__("alpha_pending",99), lambda st: st.__setitem__("alpha_settled",0)):
            state={"alpha_started":1,"ywc_v03_alpha_live":1,"alpha_ready":1,"alpha_pending":1,"ywc_v03_demo_delivery_round":1}
            run_effect(effects["ywc_v03_scheduler_reserve_alpha_normal_pending"],state,triggers)
            mutate(state); run_effect(effects["ywc_v03_scheduler_prepare_demo"],state,triggers)
            self.assertNotIn("ywc_v03_demo_reservation_arc",state)
            run_effect(effects["ywc_v03_scheduler_ack_alpha_normal_pending"],state,triggers)
            self.assertNotIn("ywc_v03_scheduler_served_alpha",state)
        lost_before_ack={"alpha_started":1,"ywc_v03_alpha_live":1,"alpha_ready":1,"alpha_pending":1,"ywc_v03_demo_delivery_round":1}
        run_effect(effects["ywc_v03_scheduler_reserve_alpha_normal_pending"],lost_before_ack,triggers)
        lost_before_ack.pop("ywc_v03_alpha_live")
        run_effect(effects["ywc_v03_scheduler_ack_alpha_normal_pending"],lost_before_ack,triggers)
        self.assertEqual(lost_before_ack["alpha_pending"],1)
        self.assertNotIn("ywc_v03_scheduler_served_alpha",lost_before_ack)
        cross={"alpha_started":1,"ywc_v03_alpha_live":1,"alpha_ready":1,"alpha_pending":1,
               "beta_started":1,"ywc_v03_beta_live":1,"beta_ready":1,"beta_pending":1,"ywc_v03_demo_delivery_round":1}
        run_effect(effects["ywc_v03_scheduler_reserve_alpha_normal_pending"],cross,triggers)
        run_effect(effects["ywc_v03_scheduler_ack_beta_normal_pending"],cross,triggers)
        self.assertEqual(cross["beta_pending"],1)
        self.assertNotIn("ywc_v03_scheduler_served_beta",cross)

    def test_test_interpreter_fails_closed_on_unknown_nested_predicate(self):
        ast=parse_script("probe = { AND = { has_variable = absent mystery_child = yes } }")
        with self.assertRaisesRegex(AssertionError,"unknown predicate"):
            eval_script(ast,"probe",{},ast)
        malformed="probe = { unknown_operator ?= yes }"
        with self.assertRaisesRegex(AssertionError,"unsupported source text"):
            parse_script(malformed)

    def test_actual_card_fields_and_unknown_source_fields_validate_strictly(self):
        source=json.loads((ROOT/"data/content/v03/countries/nqg.json").read_text(encoding="utf-8-sig"))
        source=copy.deepcopy(source)
        with self.assertRaisesRegex(ValueError,"unknown"):
            validate_catalogue_adapters(source)
        for arc in source["arcs"]:
            if arc.get("era")!="foundation": continue
            # This legacy scheduler test projects only its historical card
            # fixture fields from the NQG inline catalog. The production NQG
            # source is separately validated by the inline adapter contract.
            arc.pop("inline_delivery_adapter",None)
            jid=arc["journals"][0]["id"]; eid=arc["events"][0]["id"]
            arc["events"]=[arc["events"][0]]
            arc["delivery_adapter"]={"owner_started":f"{arc['slug']}_started","owner_settled":f"{arc['slug']}_settled","source_dispatch_effect":f"source_dispatch_{arc['slug']}",
              "live_phases":[{"journal":jid,"predicate":"{ has_variable = source_live }"}],
              "queues":[{"kind":"normal","variable":f"{arc['slug']}_pending","candidates":[{"key":"normal","event_id":eid,"value":1,"guard":"{ has_variable = source_ready }"}]}]}
        validate_catalogue_adapters(source)
        source["arcs"][0]["journals"][0]["mystery_source_field"]=True
        with self.assertRaisesRegex(ValueError,"unknown"):
            validate_catalogue_adapters(source)

    def test_queue_alias_chooser_unknown_fields_and_bool_served_fail_closed(self):
        bad=fixture_catalog(); bad["arcs"][1]["delivery_adapter"]["queues"][0]["variable"]=bad["arcs"][0]["delivery_adapter"]["queues"][0]["variable"]
        with self.assertRaisesRegex(ValueError,"aliases another owner|multiple owners|aliases another role or arc"):
            validate_catalogue_adapters(bad)
        with self.assertRaisesRegex(ValueError,"unknown arc"):
            choose_next_dispatch(("alpha",),1,{"intruder":0},{})
        with self.assertRaisesRegex(ValueError,"nonnegative integer"):
            choose_next_dispatch(("alpha",),1,{"alpha":True},{})
        with self.assertRaisesRegex(ValueError,"invalid eligible candidate"):
            choose_next_dispatch(("alpha",),1,{}, {"alpha":[{"kind":"normal","event_id":"a","mystery":1}]})

    def test_metadata_rejects_duplicate_ownership_and_shared_cooldown_candidate_gate(self):
        catalog = fixture_catalog()
        catalog["arcs"][1]["delivery_adapter"]["queues"][0]["candidates"][0]["event_id"] = "ywc_demo.1000"
        with self.assertRaisesRegex(ValueError, "foreign event|owned more than once"):
            validate_catalogue_adapters(catalog)
        catalog = fixture_catalog()
        catalog["arcs"][0]["delivery_adapter"]["queues"][0]["candidates"][0]["guard"] = "{ ywc_v03_can_deliver_major = yes }"
        with self.assertRaisesRegex(ValueError, "cooldown") :
            validate_catalogue_adapters(catalog)



_TOKENIZER=re.compile(r"var:[a-z0-9_]+|[A-Za-z][A-Za-z0-9_.]*|-?\d+|[={}>]")
_KNOWN_NATIVE_PREDICATES={f"ywc_v03_{slug}_live" for slug in ("alpha","beta","gamma")}
def parse_script(source):
    matches=list(_TOKENIZER.finditer(source)); tokens=[]; last=0
    for match in matches:
        if source[last:match.start()].strip(): raise AssertionError(f"unsupported source text: {source[last:match.start()]!r}")
        tokens.append(match.group()); last=match.end()
    if source[last:].strip(): raise AssertionError(f"unsupported source text: {source[last:]!r}")
    pos=0
    def block(expect_close=False):
        nonlocal pos
        out=[]
        while pos<len(tokens):
            if tokens[pos]=="}":
                pos+=1
                if not expect_close: raise AssertionError("unexpected close brace")
                return out
            key=tokens[pos]; pos+=1
            if pos<len(tokens) and tokens[pos]==">":
                pos+=1
                if not key.startswith("var:") or pos>=len(tokens): raise AssertionError(f"invalid > comparison after {key}")
                value=tokens[pos]; pos+=1
                if value.lstrip("-").isdigit(): value=int(value)
                out.append((">", (key,value)))
                continue
            if pos>=len(tokens) or tokens[pos]!="=": raise AssertionError(f"expected = after {key}")
            pos+=1
            if pos<len(tokens) and tokens[pos]=="{":
                pos+=1; val=block(True)
            else:
                if pos>=len(tokens): raise AssertionError("missing scalar")
                val=tokens[pos]; pos+=1
                if val.lstrip("-").isdigit(): val=int(val)
            out.append((key,val))
        if expect_close: raise AssertionError("missing close brace")
        return out
    ast=block(); assert pos==len(tokens)
    result={}
    for key,value in ast:
        if key in result: raise AssertionError(f"duplicate generated top-level definition: {key}")
        result[key]=value
    return result

def _all(ast,key): return [ast[key]] if isinstance(ast,dict) and key in ast else [v for k,v in ast if k==key]
def _validate_expr(expr,definitions):
    if not isinstance(expr,list): raise AssertionError(f"unsupported predicate shape: {expr!r}")
    for pair in expr:
        if not isinstance(pair,tuple) or len(pair)!=2: raise AssertionError(f"unsupported predicate node: {pair!r}")
        key,val=pair
        if not isinstance(key,str): raise AssertionError(f"unsupported predicate key: {key!r}")
        if key in ("AND","OR"):
            if not isinstance(val,list) or not val: raise AssertionError(f"invalid {key} predicate shape")
            _validate_expr(val,definitions)
        elif key=="NOT":
            if not isinstance(val,list) or not val: raise AssertionError("invalid NOT predicate shape")
            _validate_expr(val,definitions)
        elif key=="has_variable":
            if type(val) is not str or not re.fullmatch(r"[a-z][a-z0-9_]*",val): raise AssertionError("invalid has_variable operand")
        elif key==">":
            if (not isinstance(val,tuple) or len(val)!=2 or
                type(val[0]) is not str or not re.fullmatch(r"var:[a-z][a-z0-9_]*",val[0]) or
                not (type(val[1]) is int or type(val[1]) is str and re.fullmatch(r"var:[a-z][a-z0-9_]*",val[1]))):
                raise AssertionError("invalid > comparison shape")
        elif key.startswith("var:"):
            if not re.fullmatch(r"var:[a-z][a-z0-9_]*",key) or not (type(val) is int or type(val) is str and re.fullmatch(r"var:[a-z][a-z0-9_]*",val)):
                raise AssertionError("invalid var comparison shape")
        elif val=="yes" and key in definitions:
            _validate_expr(definitions[key],definitions)
        elif val=="yes" and key in _KNOWN_NATIVE_PREDICATES:
            pass
        else:
            raise AssertionError(f"unknown predicate or operator: {key} = {val}")

def eval_expr(expr,state,definitions):
    _validate_expr(expr,definitions) # validate every branch before boolean short-circuiting
    for key,val in expr:
        if key==">":
            left,right=val
            expected=state.get(right[4:],0) if isinstance(right,str) else right
            if state.get(left[4:],0)<=expected: return False
        elif key=="AND":
            if not all(eval_expr([node],state,definitions) for node in val): return False
        elif key=="OR":
            if not any(eval_expr([node],state,definitions) for node in val): return False
        elif key=="NOT":
            if eval_expr(val,state,definitions): return False
        elif key=="has_variable":
            if val not in state: return False
        elif key.startswith("var:"):
            expected=state.get(val[4:]) if isinstance(val,str) and val.startswith("var:") else val
            if state.get(key[4:],0)!=expected: return False
        elif val=="yes" and key in definitions:
            if not eval_expr(definitions[key],state,definitions): return False
        elif val=="yes" and key in _KNOWN_NATIVE_PREDICATES:
            if not state.get(key): return False
    return True

def eval_script(ast,name,state,definitions):
    found=_all(ast,name)
    return len(found)==1 and eval_expr(found[0],state,definitions)

def _run_block(block,state,definitions):
    for key,val in block:
        if key=="if":
            limits=_all(val,"limit")
            if len(limits)!=1: raise AssertionError("invalid if/limit shape")
            # Validate before evaluating so an unknown predicate cannot hide behind false.
            _validate_expr(limits[0],definitions)
            if eval_expr(limits[0],state,definitions): _run_block([(k,v) for k,v in val if k!="limit"],state,definitions)
        elif key=="set_variable":
            fields=dict(val)
            if set(fields)-{"name","value","days"} or not {"name","value"}<=set(fields) or type(fields["name"]) is not str: raise AssertionError("invalid set_variable shape")
            value=fields["value"]
            if isinstance(value,str) and value.startswith("var:"): value=state.get(value[4:],0)
            state[fields["name"]]=value
        elif key=="change_variable":
            fields=dict(val)
            if set(fields)!={"name","add"} or type(fields["add"]) is not int: raise AssertionError("invalid change_variable shape")
            state[fields["name"]]=state.get(fields["name"],0)+fields["add"]
        elif key=="remove_variable":
            if type(val) is not str: raise AssertionError("invalid remove_variable shape")
            state.pop(val,None)
        else: raise AssertionError(f"unsupported generated effect {key}")
def advance_test_days(state,days):
    if type(days) is not int or days<0: raise ValueError("test days must be nonnegative integer")
    timer="ywc_v03_demo_reservation_timer"
    if timer in state:
        left=state[timer]-days
        if left<=0: state.pop(timer,None)
        else: state[timer]=left
    remaining=state.get("cooldown_days",0)-days
    if remaining<=0:
        state.pop("cooldown_days",None); state.pop("ywc_v03_major_event_cooldown",None)
    else: state["cooldown_days"]=remaining

def run_effect(block,state,definitions):
    _run_block(block,state,definitions)

def _run_inline_proof(rendered,event_id,state,triggers):
    # Synthetic event-immediate boundary: parse and execute the renderer's exact
    # inline proof effect before the public ACK helper runs.
    snippets=rendered["inline_proofs"].get(event_id,[])
    if not snippets: raise AssertionError(f"no generated inline proof for {event_id}")
    wrapped=parse_script("synthetic_event_immediate = { "+" ".join(snippets)+" }")
    run_effect(wrapped["synthetic_event_immediate"],state,triggers)


def fixture_catalog():
    arcs = []
    for index, slug in enumerate(("alpha", "beta", "gamma")):
        normal_id = f"ywc_demo.{1000 + index}"
        notice_id = f"ywc_demo.{1010 + index}"
        journal_id = f"ywc_je_demo_{slug}"
        arcs.append({
            "slug": slug,
            "era": "foundation",
            "journals": [{"id": journal_id}],
            "events": [{"id": normal_id}, {"id": notice_id}],
            "delivery_adapter": {
                "owner_started": f"{slug}_started",
                "owner_settled": f"{slug}_settled",
                "source_dispatch_effect": f"ywc_demo_dispatch_{slug}",
                "live_phases": [{"journal": journal_id, "predicate": f"{{ ywc_v03_{slug}_live = yes }}"}],
                "queues": [
                    {"kind": "normal", "variable": f"{slug}_pending", "candidates": [
                        {"key": "normal_pending", "event_id": normal_id, "value": 1, "guard": f"{{ has_variable = {slug}_ready }}"}
                    ]},
                    {"kind": "notice12", "variable": f"{slug}_notice", "candidates": [
                        {"key": "notice12_pending", "event_id": notice_id, "value": 1, "guard": f"{{ has_variable = {slug}_ready }}", "acknowledgement": ([{"op":"set","variable":"alpha_ack_seen","value":1}] if slug=="alpha" else [])}
                    ]},
                ],
            },
        })
    return {"key": "demo", "runtime_tags": ["DEMO"], "arcs": arcs}


if __name__ == "__main__":
    unittest.main()
