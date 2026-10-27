"""NMG's optional, separately accepted market authority; offline source model."""
import unittest
from pathlib import Path

from clausewitz_harness import parse
from shu_kor_strict_review_runtime import field
from test_v03_nmg_partner_response import NmgPartnerWorld, accepted_fixed, base_countries
from kor_partner_protocol_runtime import CountryRef, UnsupportedSubset, _MISSING

DECISION = Path("yongchang_world/common/decisions/ywc_v03_nmg_market_autonomy.txt")
PACT = "ywc_nmg_mex_market_control"


class MarketWorld(NmgPartnerWorld):
    """Model only the authored bilateral pact and market owner, not trade."""
    def __init__(self, countries):
        super().__init__(countries)
        self.market_pacts = set()
        self.reject_creation = False

    def condition(self, node, tag):
        key, op, value = node
        if key in ("is_direct_subject_of", "is_diplomatic_play_enemy_of", "market.owner", "has_diplomatic_pact"):
            if self._current is None:
                with self._chain(self.country_ref(tag)):
                    return self.condition(node, tag)
            if key == "is_direct_subject_of":
                return self.countries[tag].get("direct_subject", True) and super().condition(("is_subject_of", op, value), tag)
            if key == "is_diplomatic_play_enemy_of":
                if op != "=": raise UnsupportedSubset("unsupported diplomatic enemy operator")
                other = self._value(value, optional=True)
                return isinstance(other, CountryRef) and other.tag in self.countries[tag].get("diplo_play_enemies", [])
            if key == "market.owner":
                left = self._value("market.owner", optional=True)
                right = self._value(value, optional=True)
                return left is not _MISSING and right is not _MISSING and self.compare(left, op, right)
            if op != "=": raise UnsupportedSubset("unsupported pact predicate")
            fields = self._fields(value, {"who", "type"}, {"who", "type"})
            other = self._value(fields["who"], optional=True)
            if other is _MISSING: return False
            return any(kind == fields["type"] and {actor, target} == {self._current, other}
                       for actor, target, kind in self.market_pacts)
        return super().condition(node, tag)

    def execute(self, nodes, tag):
        # Keep if/else chains intact; only split around the one supported effect.
        if not any(key == "create_diplomatic_pact" for key, _, _ in nodes):
            return super().execute(nodes, tag)
        if self._current is None:
            with self._chain(self.country_ref(tag)):
                return self.execute(nodes, tag)
        chunk = []
        for key, op, body in nodes:
            if key != "create_diplomatic_pact":
                chunk.append((key, op, body)); continue
            if chunk:
                super().execute(chunk, tag); chunk = []
            if op != "=": raise UnsupportedSubset("unsupported create pact operator")
            fields = self._fields(body, {"country", "type"}, {"country", "type"})
            target = self._value(fields["country"])
            if fields["type"] != PACT or not isinstance(target, CountryRef) or not isinstance(self._current, CountryRef):
                raise UnsupportedSubset("unsupported diplomatic pact")
            if not self.reject_creation:
                self.market_pacts.add((self._current, target, fields["type"]))
                # An explicit bounded interpretation of market_owner=second_country.
                self.countries[target.tag]["market"] = f"m_{target.tag}"
                self.markets.setdefault(f"m_{target.tag}", {"owner": target.tag, "adjacent": set()})["owner"] = target.tag
        if chunk: super().execute(chunk, tag)

    def run_pact_maintenance(self):
        path = Path("yongchang_world/common/diplomatic_actions/ywc_v03_nmg_market_autonomy.txt")
        action = next(body for key, _, body in parse(path.read_text(encoding="utf-8-sig")) if key == PACT)
        rule = field(field(field(action, "pact"), "requirement_to_maintain"), "trigger")
        for actor, target, kind in list(self.market_pacts):
            if kind != PACT: continue
            if not self._present(actor) or not self._present(target):
                self.market_pacts.remove((actor, target, kind)); continue
            with self._chain(actor, (("target_country", target),)):
                if not self.conditions(rule, actor.tag):
                    self.market_pacts.remove((actor, target, kind))


def decision():
    return next(body for key, _, body in parse(DECISION.read_text(encoding="utf-8-sig"))
                if key == "ywc_nmg_request_market_autonomy")


def eligible_world():
    countries = base_countries()
    countries["NMG"]["market"] = "m_MEX"
    world = MarketWorld(countries)
    accepted_fixed(world)
    world.run_country_monthly("NMG")
    assert countries["NMG"]["ywc_nmg_mexshare_paid_total"] > 0
    return world, countries


class NmgMarketAutonomyTests(unittest.TestCase):
    def test_payment_and_both_country_decisions_are_needed_for_the_market_right(self):
        world, countries = eligible_world()
        self.assertTrue(world.conditions(field(decision(), "possible"), "NMG"))
        world.execute(field(decision(), "when_taken"), "NMG")
        offer = world.jobs[-1]
        self.assertEqual(offer.event_id, "ywc_nmg.1033")
        self.assertEqual(offer.recipient, world.country_ref("MEX"))
        self.assertNotIn("ywc_nmg_market_granted_generation", countries["NMG"])
        self.assertTrue(world.display_job(offer))
        self.assertTrue(world.job_options(offer)["accept"])
        world.choose_job(offer, "accept")
        self.assertEqual(countries["NMG"]["ywc_nmg_market_granted_generation"],
                         countries["NMG"]["ywc_nmg_mexshare_contract_generation"])
        self.assertTrue(world.conditions(parse("has_diplomatic_pact = { who = c:MEX type = " + PACT + " }"), "NMG"))

    def test_request_requires_real_paid_current_direct_shared_market_contract(self):
        countries = base_countries(); countries["NMG"]["market"] = "m_MEX"
        world = MarketWorld(countries)
        self.assertFalse(world.conditions(field(decision(), "is_shown"), "NMG"))
        self.assertFalse(world.conditions(field(decision(), "possible"), "NMG"))
        accepted_fixed(world)
        self.assertFalse(world.conditions(field(decision(), "possible"), "NMG"), "unpaid signed contract is insufficient")
        world.run_country_monthly("NMG")
        self.assertTrue(world.conditions(field(decision(), "possible"), "NMG"))
        for change, undo in (
            (lambda: countries["NMG"].update({"direct_subject": False}), lambda: countries["NMG"].pop("direct_subject")),
            (lambda: countries["NMG"].update({"is_subject": False}), lambda: countries["NMG"].update({"is_subject": True})),
            (lambda: countries["NMG"].update({"market": "m_NMG"}), lambda: countries["NMG"].update({"market": "m_MEX"})),
            (lambda: world.markets.setdefault("m_MEX", {"owner": None, "adjacent": set()}).update({"owner": "JHG"}), lambda: world.markets["m_MEX"].update({"owner": "MEX"})),
            (lambda: countries["NMG"].update({"diplo_play_enemies": ["MEX"]}), lambda: countries["NMG"].pop("diplo_play_enemies")),
            (lambda: countries["NMG"].update({"in_default": True}), lambda: countries["NMG"].update({"in_default": False})),
            (lambda: countries["NMG"].update({"ywc_nmg_mexshare_earned_total": 40}), lambda: countries["NMG"].update({"ywc_nmg_mexshare_earned_total": 20})),
        ):
            change()
            self.assertFalse(world.conditions(field(decision(), "possible"), "NMG"))
            undo()
            self.assertTrue(world.conditions(field(decision(), "possible"), "NMG"))

    def test_refusal_and_cooldown_do_not_change_the_debt_or_market(self):
        world, countries = eligible_world()
        before = (countries["NMG"]["ywc_nmg_mexshare_contract_generation"],
                  countries["NMG"]["ywc_nmg_mexshare_paid_total"], world.treasury["MEX"])
        world.execute(field(decision(), "when_taken"), "NMG")
        offer = world.jobs[-1]
        self.assertTrue(world.display_job(offer)); world.choose_job(offer, "refuse")
        self.assertEqual(countries["NMG"]["market"], "m_MEX")
        self.assertEqual(world.market_pacts, set())
        self.assertEqual((countries["NMG"]["ywc_nmg_mexshare_contract_generation"],
                          countries["NMG"]["ywc_nmg_mexshare_paid_total"], world.treasury["MEX"]), before)
        self.assertFalse(world.conditions(field(decision(), "possible"), "NMG"))
        world.advance_months(6); world.run_country_monthly("NMG")
        self.assertTrue(world.conditions(field(decision(), "possible"), "NMG"))

    def test_old_offer_cannot_be_revived_by_a_subject_change_and_reversal(self):
        world, countries = eligible_world()
        world.execute(field(decision(), "when_taken"), "NMG")
        offer = world.jobs[-1]; self.assertTrue(world.display_job(offer))
        countries["NMG"]["is_subject"] = False
        world.run_on_action("on_become_independent", "NMG")
        countries["NMG"]["is_subject"] = True
        self.assertFalse(world.job_options(offer)["accept"])
        world.choose_job(offer, "accept")
        self.assertEqual(world.market_pacts, set())
        self.assertNotIn("ywc_nmg_market_granted_generation", countries["NMG"])

    def test_old_offer_rejects_changed_contract_market_or_new_mexico_object(self):
        for mutation in ("generation", "monthly", "market", "mexico"):
            with self.subTest(mutation=mutation):
                world, countries = eligible_world()
                world.execute(field(decision(), "when_taken"), "NMG")
                offer = world.jobs[-1]; self.assertTrue(world.display_job(offer))
                if mutation == "generation": countries["NMG"]["ywc_nmg_mexshare_contract_generation"] += 1
                if mutation == "monthly": countries["NMG"]["ywc_nmg_mexshare_contract_monthly"] += 1
                if mutation == "market": countries["NMG"]["market"] = "m_NMG"
                if mutation == "mexico":
                    world.remove_country("MEX"); world.add_country("MEX", base_countries()["MEX"])
                self.assertFalse(world.job_options(offer).get("accept", False))
                world.choose_job(offer, "accept")
                self.assertEqual(world.market_pacts, set())
                self.assertNotIn("ywc_nmg_market_granted_generation", countries["NMG"])

    def test_market_change_seen_by_monthly_check_invalidates_old_offer(self):
        world, countries = eligible_world()
        world.execute(field(decision(), "when_taken"), "NMG")
        offer = world.jobs[-1]; self.assertTrue(world.display_job(offer))
        countries["NMG"]["market"] = "m_NMG"
        world.run_country_monthly("NMG")
        countries["NMG"]["market"] = "m_MEX"
        self.assertFalse(world.job_options(offer)["accept"])
        world.choose_job(offer, "accept")
        self.assertEqual(world.market_pacts, set())

    def test_monthly_check_catches_both_countries_changing_to_a_new_market(self):
        world, countries = eligible_world()
        world.execute(field(decision(), "when_taken"), "NMG")
        offer = world.jobs[-1]; self.assertTrue(world.display_job(offer))
        world.markets["m_new"] = {"owner": "MEX", "adjacent": set()}
        countries["NMG"]["market"] = countries["MEX"]["market"] = "m_new"
        world.run_country_monthly("NMG")
        countries["NMG"]["market"] = countries["MEX"]["market"] = "m_MEX"
        self.assertFalse(world.job_options(offer)["accept"], "a detected change must invalidate the old request")
        world.choose_job(offer, "accept")
        self.assertEqual(world.market_pacts, set())

    def test_market_aba_between_checks_is_a_documented_observation_limit(self):
        world, countries = eligible_world()
        world.execute(field(decision(), "when_taken"), "NMG")
        offer = world.jobs[-1]; self.assertTrue(world.display_job(offer))
        countries["NMG"]["market"] = "m_NMG"
        countries["NMG"]["market"] = "m_MEX"
        # No observed callback or monthly check saw the intermediate change.
        self.assertTrue(world.job_options(offer)["accept"])

    def test_pact_creation_failure_never_records_a_grant_or_changes_the_ledger(self):
        world, countries = eligible_world(); world.reject_creation = True
        before = (countries["NMG"]["ywc_nmg_mexshare_earned_total"],
                  countries["NMG"]["ywc_nmg_mexshare_paid_total"])
        world.execute(field(decision(), "when_taken"), "NMG")
        offer = world.jobs[-1]; self.assertTrue(world.display_job(offer)); world.choose_job(offer, "accept")
        self.assertEqual(world.market_pacts, set())
        self.assertNotIn("ywc_nmg_market_granted_generation", countries["NMG"])
        self.assertEqual(countries["NMG"]["ywc_nmg_market_request_state"], 4)
        self.assertEqual((countries["NMG"]["ywc_nmg_mexshare_earned_total"],
                          countries["NMG"]["ywc_nmg_mexshare_paid_total"]), before)

    def test_current_paid_pact_survives_war_or_negative_income_until_payment_is_missed(self):
        for disruption in ("war", "income", "relations", "default"):
            with self.subTest(disruption=disruption):
                world, countries = eligible_world()
                world.execute(field(decision(), "when_taken"), "NMG")
                offer = world.jobs[-1]; self.assertTrue(world.display_job(offer)); world.choose_job(offer, "accept")
                if disruption == "war": countries["NMG"]["is_at_war"] = True
                if disruption == "income": countries["NMG"]["net_fixed_income"] = -1
                if disruption == "default": countries["NMG"]["in_default"] = True
                if disruption == "relations": countries["MEX"]["relations"]["NMG"] = -5
                self.assertEqual(countries["NMG"]["ywc_nmg_mexshare_earned_total"], countries["NMG"]["ywc_nmg_mexshare_paid_total"])
                world.run_pact_maintenance()
                self.assertEqual(len(world.market_pacts), 1, "a paid obligation cannot be revoked merely because future payment may be harder")

    def test_maintenance_breaks_only_our_pact_on_arrears_without_forgiving_debt(self):
        world, countries = eligible_world()
        world.execute(field(decision(), "when_taken"), "NMG")
        offer = world.jobs[-1]; self.assertTrue(world.display_job(offer)); world.choose_job(offer, "accept")
        unrelated = (world.country_ref("MEX"), world.country_ref("NMG"), "unrelated_pact")
        world.market_pacts.add(unrelated)
        world.run_pact_maintenance()
        self.assertEqual(len(world.market_pacts), 2)
        countries["NMG"]["in_default"] = True
        world.advance_months(1); world.run_country_monthly("NMG")
        self.assertGreater(countries["NMG"]["ywc_nmg_mexshare_earned_total"], countries["NMG"]["ywc_nmg_mexshare_paid_total"])
        world.run_pact_maintenance()
        self.assertEqual(world.market_pacts, {unrelated})
        countries["NMG"]["in_default"] = False
        world.advance_months(1); world.run_country_monthly("NMG")
        self.assertEqual(countries["NMG"]["ywc_nmg_mexshare_earned_total"], countries["NMG"]["ywc_nmg_mexshare_paid_total"])
        world.run_pact_maintenance()
        self.assertEqual(world.market_pacts, {unrelated}, "cure must not recreate a pact without new consent")

    def test_maintenance_ends_on_old_generation_expiry_or_subject_loss(self):
        for invalidation in ("end", "subject", "generation", "partner"):
            with self.subTest(invalidation=invalidation):
                world, countries = eligible_world()
                world.execute(field(decision(), "when_taken"), "NMG")
                offer = world.jobs[-1]; self.assertTrue(world.display_job(offer)); world.choose_job(offer, "accept")
                if invalidation == "end": world.advance_months(60)
                if invalidation == "subject": countries["NMG"]["is_subject"] = False
                if invalidation == "generation": countries["NMG"]["ywc_nmg_mexshare_contract_generation"] += 1
                if invalidation == "partner": world.remove_country("MEX")
                world.run_pact_maintenance()
                self.assertEqual(world.market_pacts, set())

    def test_existing_vanilla_market_pacts_are_neither_replaced_nor_removed(self):
        for kind in ("grant_own_market", "request_market_control", PACT):
            with self.subTest(kind=kind):
                world, _ = eligible_world()
                existing = (world.country_ref("MEX"), world.country_ref("NMG"), kind)
                world.market_pacts.add(existing)
                self.assertFalse(world.conditions(field(decision(), "possible"), "NMG"))
                world.execute(field(decision(), "when_taken"), "NMG")
                self.assertEqual(world.market_pacts, {existing})

    def test_expired_offer_is_cancelled_and_cannot_be_replayed(self):
        world, countries = eligible_world()
        world.execute(field(decision(), "when_taken"), "NMG")
        offer = world.jobs[-1]; self.assertTrue(world.display_job(offer))
        world.advance_months(3); world.run_country_monthly("NMG")
        self.assertEqual(countries["NMG"]["ywc_nmg_market_request_state"], 3)
        self.assertFalse(world.job_options(offer)["accept"])
        world.choose_job(offer, "accept")
        self.assertEqual(world.market_pacts, set())
        self.assertFalse(world.conditions(field(decision(), "possible"), "NMG"))
        world.advance_months(3); world.run_country_monthly("NMG")
        self.assertTrue(world.conditions(field(decision(), "possible"), "NMG"))

    def test_repeated_acceptance_is_idempotent_and_does_not_change_remittance(self):
        world, countries = eligible_world()
        before = (countries["NMG"]["ywc_nmg_mexshare_paid_total"],
                  countries["NMG"]["ywc_nmg_mexshare_contract_monthly"], world.treasury["MEX"])
        world.execute(field(decision(), "when_taken"), "NMG")
        offer = world.jobs[-1]; self.assertTrue(world.display_job(offer))
        world.choose_job(offer, "accept"); world.choose_job(offer, "accept")
        self.assertEqual(len(world.market_pacts), 1)
        self.assertEqual((countries["NMG"]["ywc_nmg_mexshare_paid_total"],
                          countries["NMG"]["ywc_nmg_mexshare_contract_monthly"], world.treasury["MEX"]), before)
        self.assertEqual(countries["NMG"]["market"], "m_NMG")

    def test_cured_arrears_require_a_new_offer_and_new_mexican_consent(self):
        world, countries = eligible_world()
        world.execute(field(decision(), "when_taken"), "NMG")
        old = world.jobs[-1]; self.assertTrue(world.display_job(old)); world.choose_job(old, "accept")
        countries["NMG"]["in_default"] = True
        world.advance_months(1); world.run_country_monthly("NMG"); world.run_pact_maintenance()
        self.assertEqual(world.market_pacts, set())
        countries["NMG"]["in_default"] = False
        # The test explicitly supplies the later shared-market condition; it
        # does not infer how the game reorganizes a market after pact removal.
        countries["NMG"]["market"] = "m_MEX"
        for _ in range(5):
            world.advance_months(1); world.run_country_monthly("NMG")
        self.assertEqual(countries["NMG"]["ywc_nmg_mexshare_earned_total"], countries["NMG"]["ywc_nmg_mexshare_paid_total"])
        self.assertTrue(world.conditions(field(decision(), "possible"), "NMG"))
        world.execute(field(decision(), "when_taken"), "NMG")
        new = world.jobs[-1]; self.assertNotEqual(new, old)
        self.assertTrue(world.display_job(new))
        self.assertEqual(world.market_pacts, set())
        world.choose_job(old, "accept")
        self.assertEqual(world.market_pacts, set())
        world.choose_job(new, "accept")
        self.assertEqual(len(world.market_pacts), 1)

    def test_market_request_does_not_consume_or_replace_the_normal_revenue_queue(self):
        world, countries = eligible_world()
        countries["NMG"]["ywc_nmg_revenue_pending"] = 1021
        before = {key: value for key, value in countries["NMG"].items() if key.startswith("ywc_nmg_revenue_")}
        world.execute(field(decision(), "when_taken"), "NMG")
        offer = world.jobs[-1]; self.assertTrue(world.display_job(offer)); world.choose_job(offer, "accept")
        self.assertEqual({key: value for key, value in countries["NMG"].items() if key.startswith("ywc_nmg_revenue_")}, before)
        self.assertEqual(countries["NMG"]["ywc_nmg_revenue_pending"], 1021)

    def test_decision_remains_available_after_the_story_arc_settles(self):
        world, countries = eligible_world()
        countries["NMG"]["ywc_v03_nmg_v03_nmg_autonomy_revenue_settled"] = 1
        self.assertTrue(world.conditions(field(decision(), "is_shown"), "NMG"))
        self.assertTrue(world.conditions(field(decision(), "possible"), "NMG"))
        world.execute(field(decision(), "when_taken"), "NMG")
        self.assertEqual(world.jobs[-1].event_id, "ywc_nmg.1033")

    def test_offer_displays_remaining_original_term_not_a_new_sixty_month_term(self):
        world, countries = eligible_world()
        for _ in range(59):
            world.advance_months(1); world.run_country_monthly("NMG")
        world.execute(field(decision(), "when_taken"), "NMG")
        offer = world.jobs[-1]
        self.assertEqual(dict(offer.saved)["ywc_nmg_market_remaining_months"], 1)
        self.assertTrue(world.display_job(offer)); world.choose_job(offer, "accept")
        self.assertEqual(len(world.market_pacts), 1)
        world.advance_months(1); world.run_pact_maintenance()
        self.assertEqual(world.market_pacts, set())

    def test_pact_and_decision_describe_their_actual_scope(self):
        action = parse(Path("yongchang_world/common/diplomatic_actions/ywc_v03_nmg_market_autonomy.txt").read_text(encoding="utf-8-sig"))
        pact = field(next(body for key, _, body in action if key == PACT), "pact")
        self.assertEqual(field(pact, "market_owner"), "second_country")
        self.assertEqual(field(pact, "forced_duration"), "0")
        for language in ("english", "simp_chinese"):
            text = Path(f"yongchang_world/localization/{language}/ywc_v03_nmg_market_autonomy_l_{language}.yml").read_text(encoding="utf-8-sig")
            self.assertIn("ywc_nmg_request_market_autonomy_desc:", text)
            self.assertIn("ywc_nmg_request_market_autonomy_tooltip:", text)
            self.assertIn("ywc_nmg_mex_market_control_desc:", text)
            self.assertIn("ywc_nmg_mex_market_control_pact_desc:", text)


if __name__ == "__main__":
    unittest.main()
