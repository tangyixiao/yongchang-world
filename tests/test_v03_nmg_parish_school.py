"""Actual-source business tests for the frozen NMG parish-school middle card.

Frozen contract: ``docs/superpowers/plans/2026-10-30-nmg-parish-school.md``.
That binding plan overrides the earlier design draft: no fake parish funds, no
extra notice flow, no outcome restriction. This module reads only authored
source that the root generator is due to add; it never copies a stage machine
into Python and never injects a positive historical outcome, fee, streak,
receipt or queue entry to advance a run.

Business scenarios require the authored arc. The declared-card selector never
skips, preserving a genuine missing-feature RED before implementation. Field
suffixes not fixed by the plan must be checked against the final authored source
before business acceptance; a prepared assertion is not runtime evidence.

Reused runtime facts (proven by ``test_v03_nmg_school_runtime``):

* ``NmgSchoolWorld`` loads the real NMG source, typed country/state references
  and the Gregorian calendar; ``LanPublicWorld`` adds same-IG/employed-pop facts.
* ``literal_countries()`` supplies ordinary engine facts; the NMG pilot's real state must be
  present on the ``countries`` dict *before* construction, because
  ``PartnerWorld`` assigns world-unique state identities then. Never replace the
  state arrays afterwards with unregistered copies.
* ``PartnerWorld.advance_months`` owns ``elapsed_months`` itself; ``month`` does
  not increment it a second time.
* Every inherited low-level API is called with an explicit ``"NMG"`` tag.

This module only proves an offline source/fact composition. It is not an
engine, UI, save-game, AI, performance or balance acceptance.
"""
import copy
from datetime import date
import json
from pathlib import Path
import unittest

from nmg_school_runtime import NmgSchoolWorld
from kor_partner_protocol_runtime import StateRef
from shu_kor_strict_review_runtime import field
from test_v03_nmg_school_runtime import (
    earn_old_office, new_world as producer_world,
    literal_countries as producer_countries,
)


ROOT = Path(__file__).resolve().parents[1]

# Frozen identifiers from the binding plan (not yet present in the tree).
SLUG = "v03_nmg_parish_school"
JE1 = "ywc_je_v03_nmg_parish_school"
JE2 = "ywc_je_v03_nmg_parish_settlement"
QUEUE = "ywc_nmg_school_pending_event"
P = "ywc_nmg_school_"
L = "ywc_v03_nmg_v03_nmg_parish_school_"
RECEIPT = L + "last_event"
JES = (JE1, JE2)
MODES = {1: "joint_school", 2: "parish_split", 3: "secular_coordination"}
EVENTS = tuple(f"ywc_nmg.{n}" for n in range(1110, 1118))
RESERVED_EVENTS = ("ywc_nmg.1118", "ywc_nmg.1119")

# Current-fact carriers that may legitimately change between helper calls. A
# negative control changes one of these; earned business values never are.
CURRENT_KEYS = (
    "laws", "institutions", "states", "igs", "literacy_rate", "bureaucracy",
    "net_fixed_income", "legitimacy", "authority", "is_at_war", "in_default",
    "yearly_gross_income", "gold_reserves", "is_subject", "overlord", "market",
)

# The real old bilingual office prefix proven by the runtime suite.
OLD_PREFIX = "ywc_v03_nmg_v03_nmg_bilingual_office_"
OLD_JE = "ywc_je_flavor_nmg_bargain_1"
OLD_EVENTS = ("ywc_nmg.6", "ywc_nmg.100", "ywc_nmg.101",
              "ywc_nmg.102", "ywc_nmg.103", "ywc_nmg.104")


# --------------------------------------------------------------------------- #
# Current engine facts; no business grant is present in the factory.          #
# --------------------------------------------------------------------------- #
def literal_countries(*, mode=1, bare=False, schools=None, laws=None,
                      office_occupancy=None, academics_occupancy=None):
    """Ordinary current engine facts for the real NMG Baja pilot.

    No business flags are present. Offices represent the current mod sources
    (``bureaucrats``, ``academics``, ``clergymen``) with real workplaces, and
    ``schools`` is the current school investment level, never a made-up parish
    fund. Optional keyword arguments exist only so negative controls can vary a
    single present fact.
    """
    if type(mode) is not int or mode not in MODES:
        raise ValueError(mode)
    state = producer_countries()["NMG"]
    controlled = {"law_no_schools", "law_public_schools", "law_private_schools",
                  "law_religious_schools", "law_state_religion",
                  "law_freedom_of_conscience", "law_total_separation"}
    selected = {1: ("law_public_schools", "law_freedom_of_conscience"),
                2: ("law_religious_schools", "law_state_religion"),
                3: ("law_public_schools", "law_total_separation")}[mode] if laws is None else laws
    state["laws"] = [law for law in state["laws"] if law not in controlled]
    state["laws"].extend(law for law in selected if law not in state["laws"])
    state["institutions"] = {"institution_schools": (2 if mode == 3 else 1) if schools is None else schools}
    state["igs"] = [
        {"type": kind, "in_government": True, "clout": .15, "approval": 1}
        for kind in ("ig_intelligentsia", "ig_devout", "ig_petty_bourgeoisie",
                     "ig_rural_folk")
    ]
    province = state["states"][0]
    province.update(owner="NMG", region="s:STATE_BAJA_CALIFORNIA")
    office = next(building for building in province["buildings"]
                  if building["type"] == "building_government_administration")
    university = next(building for building in province["buildings"]
                      if building["type"] == "building_university")
    office["occupancy"] = (.8 if mode == 3 else .5) if office_occupancy is None else office_occupancy
    university["occupancy"] = (.5 if mode == 2 else .8) if academics_occupancy is None else academics_occupancy
    for building in province["buildings"]:
        building["level"] = 1
    bureaucrat = province["pops"][0]
    bureaucrat.update(type="bureaucrats", employed=True, workplace=office,
                      acceptance=5, primary=False)
    academics = copy.deepcopy(bureaucrat)
    academics.update(type="academics", workplace=university)
    clergymen = copy.deepcopy(bureaucrat)
    clergymen.update(type="clergymen", workplace=university)
    province["pops"] = [bureaucrat, academics, clergymen]
    if bare:
        state["laws"] = ["law_monarchy", "law_autocracy", "law_state_religion", "law_no_schools", "law_serfdom"]
        state["institutions"] = {"institution_schools": 0}
        office["occupancy"] = .25
        province["buildings"], province["pops"] = [office], [bureaucrat]
        for candidate in state["igs"]:
            candidate["in_government"] = False
    foreign = copy.deepcopy(state)
    foreign.update(is_subject=False, overlord=None, relations={"NMG": 50},
                   market="m_mex")
    foreign["states"][0].update(owner="MEX", region="s:STATE_CALIFORNIA")
    foreign["institutions"]["institution_schools"] = 4
    return {"NMG": state, "MEX": foreign}


def new_world(countries=None, *, mode=1, bare=False, start_date=date(1836, 1, 1)):
    """Build the proven same-world fact layer with full states at construction."""
    countries = literal_countries(mode=mode, bare=bare) if countries is None else countries
    world = NmgSchoolWorld(countries, start_date=start_date)
    world.run("ywc_v03_initialize_country", "NMG")
    world._school_fixture_mode = mode
    world._school_handled_jobs = {job.serial for job in world.jobs}
    world._school_country_month = None
    return world


def school_arc(catalog):
    """Return the authored parish-school arc, or ``None`` while it is absent."""
    return next((arc for arc in catalog.get("arcs", []) if arc.get("slug") == SLUG),
                None)


def has_arc(world):
    return school_arc(world.cat) is not None


def has_declared_arc():
    """Read the authored NMG catalog file directly; no world is constructed."""
    path = ROOT / "data/content/v03/countries/nmg.json"
    if not path.exists():
        return False
    catalog = json.loads(path.read_text(encoding="utf-8"))
    return school_arc(catalog) is not None


def requires_arc(function):
    """Skip a business method cleanly while the authored arc is still absent.

    The check reads the authored catalog file directly so importing/collecting
    this module never constructs a world or touches future helpers. It returns
    ``True`` only once the root generator has written the arc.
    """
    present = has_declared_arc()
    return unittest.skipUnless(
        present, "parish-school source arc not yet generated")(function)


def world_facts(world):
    """Copy only the current-fact carriers; never the earned business values."""
    state = world.countries[world.tag]
    return copy.deepcopy({key: state[key] for key in CURRENT_KEYS if key in state and key != "gold_reserves"})


def current_facts(mode=1, bare=False):
    return literal_countries(mode=mode, bare=bare)["NMG"]


def apply_current_facts(world, mode=1, bare=False, *, office_occupancy=None,
                        academics_occupancy=None, available_cash=100000):
    state = world.countries["NMG"]
    earned = copy.deepcopy({key: value for key, value in state.items() if key.startswith("ywc_")})
    current = literal_countries(mode=mode, bare=bare, office_occupancy=office_occupancy,
                                academics_occupancy=academics_occupancy)["NMG"]
    original = state["states"][0]
    identity = original["_sid"]
    replacement = copy.deepcopy(current.pop("states")[0])
    original.clear()
    original.update(replacement, _sid=identity)
    state.update({key: value for key, value in current.items() if key != "gold_reserves"})
    set_cash(world, available_cash)
    assert {key: state[key] for key in earned} == earned
    world._school_fixture_mode = mode
    world._school_handled_jobs = {job.serial for job in world.jobs}
    world._school_country_month = None


def old_office_world(outcome=3, *, academics_occupancy=.5):
    world = producer_world()
    if outcome is None:
        world.run("ywc_v03_initialize_country", "NMG")
    else:
        earn_old_office(world, outcome)
    apply_current_facts(world, office_occupancy=.8, academics_occupancy=academics_occupancy)
    return world


def cash(world):
    """Native-visible reserve plus the real paid treasury (one honest balance)."""
    state = world.countries[world.tag]
    return state["gold_reserves"] + world.treasury[world.tag]


def set_cash(world, amount):
    """Express an affordable balance through the actual reserve + treasury pair."""
    state = world.countries[world.tag]
    state["gold_reserves"] = amount - world.treasury[world.tag]


def office(world):
    return next(b for b in world.countries[world.tag]["states"][0]["buildings"]
                if b["type"] == "building_government_administration")


def university(world):
    return next(b for b in world.countries[world.tag]["states"][0]["buildings"]
                if b["type"] == "building_university")


def employed_pop(world, kind):
    return next(p for p in world.countries[world.tag]["states"][0]["pops"]
                if p["type"] == kind)


def group(world, kind):
    return next(g for g in world.countries[world.tag]["igs"] if g["type"] == kind)


def option_nodes(event, key):
    return next(body for name, _, body in event
                if name == "option" and field(body, "name").endswith("." + key))


def option_legal(world, event, key):
    job = world._school_event_jobs[id(event)]
    with world._chain(job.recipient, world._displayed[job]):
        return world.conditions(field(option_nodes(event, key), "trigger"), world.tag)


def _option_effect(nodes):
    result = []
    for node in nodes:
        key, _, value = node
        if key == "custom_tooltip":
            result.extend(child for child in value if child[0] != "text")
        elif key not in ("name", "trigger", "ai_chance", "custom_tooltip", "default_option"):
            result.append(node)
    return result


def force_option(world, event, key):
    """Execute the full authored option effect even after visibility change."""
    job = world._school_event_jobs[id(event)]
    with world._chain(job.recipient, world._displayed[job]):
        world.execute(_option_effect(option_nodes(event, key)), world.tag)


def choose(world, arc, event, key):
    assert option_legal(world, event, key), ("illegal_option", key,
                                             field(event, "id"))
    force_option(world, event, key)
    world.refresh(arc)


def play(world, arc, number, key):
    """Deliver one authored event by its real number and select an actual option."""
    event = deliver(world, arc, number)
    choose(world, arc, event, key)
    return event


def month(world, arc, count=1):
    """Advance real Gregorian months; PartnerWorld owns the elapsed counter."""
    for _ in range(count):
        world.advance_months(1)
        _country_monthly_once(world)
        world.pulse(arc)


def _country_monthly_once(world):
    if world._school_country_month != world.date:
        world.run_country_monthly("NMG")
        world._school_country_month = world.date


def deliver(world, arc, number):
    wanted = number if isinstance(number, str) else f"ywc_nmg.{number}"
    for _ in range(72):
        _country_monthly_once(world)
        world.pulse(arc)
        for job in world.jobs:
            if job.serial in world._school_handled_jobs or not world.display_job(job):
                continue
            world._school_handled_jobs.add(job.serial)
            if job.event_id != wanted:
                raise AssertionError(("unexpected_actual_school_job", wanted, job.event_id))
            event = world.event_defs[job.event_id]
            world.__dict__.setdefault("_school_event_jobs", {})[id(event)] = job
            return event
        world.advance_months(1)
    raise AssertionError(("no_actual_school_job", wanted, world.date))


# Option keys below come from the frozen plan, without a Python stage machine.
ACTIONS = {1110: "joint_school", 1111: "pay_register", 1112: "hire_academic",
           1113: "sign_curriculum", 1114: "pay_wages", 1115: "audit_teaching_duties",
           1116: "request_full", 1117: "close_full"}
LIMITED_SELECT = "limited_classroom"


def ready_for_review(world, *, mode=None, limited=False, teacher=None, number_through=1115):
    """Drive genuine authored events up to (and including) the given stage.

    No business value is seeded: each step selects an actual option whose
    trigger the source itself exposes. Returns the arc.
    """
    arc = school_arc(world.cat)
    assert arc is not None, "parish-school arc absent"
    mode = world._school_fixture_mode if mode is None else mode
    teacher = teacher or ("local_instructor" if limited else "appoint_clergy" if mode == 2 else "hire_academic")
    plan = [(1110, LIMITED_SELECT if limited else MODES[mode]),
            (1111, ACTIONS[1111]),
            (1112, teacher),
            (1113, ACTIONS[1113]),
            (1114, ACTIONS[1114]),
            (1115, ACTIONS[1115])]
    for number, key in plan:
        if number > number_through:
            break
        play(world, arc, number, key)
    return arc


def finish_review(world, arc, outcome=1):
    """Request and close after the caller actually earned six monthly ticks."""
    suffix = {1: "full", 2: "limited", 3: "setback"}[outcome]
    play(world, arc, 1116, "request_" + suffix)
    play(world, arc, 1117, "close_" + suffix)


# --------------------------------------------------------------------------- #
# The one non-skipping method: the declared card contract (initial true RED).  #
# --------------------------------------------------------------------------- #
class DeclaredSchoolCardContract(unittest.TestCase):
    def test_declared_school_card_contract(self):
        """Assert the declared card exists; this is the initial true RED selector.

        The root runner can select this single method to obtain a real
        missing-feature RED before any source author edits. It fails loudly
        while the arc is absent and never skips.
        """
        world = new_world()
        arc = school_arc(world.cat)
        self.assertIsNotNone(
            arc, f"authored catalog must declare arc {SLUG!r} before any flow")
        events = [e["id"] for e in arc["events"]]
        self.assertEqual(tuple(events), EVENTS,
                         "authored card must expose exactly 1110..1117")
        self.assertEqual(RESERVED_EVENTS[0] in events, False)
        self.assertEqual(RESERVED_EVENTS[1] in events, False)
        journals = [journal["id"] for journal in arc["journals"]]
        self.assertEqual(tuple(journals), (JE1, JE2),
                         "two journals: school 1110..1113, settlement 1114..1117")
        self.assertIn(JE1, world.journal_defs)
        self.assertIn(JE2, world.journal_defs)
        # No extra notice arc / event is admitted by the frozen card.
        self.assertFalse(any(e.get("hidden", False) in (True, "yes") for e in arc["events"]),
                         "card adds no extra notice events")


# --------------------------------------------------------------------------- #
# Business scenarios (skipped until the authored arc exists).                 #
# --------------------------------------------------------------------------- #
class NmgParishSchoolBusiness(unittest.TestCase):
    def _world(self, mode=1, bare=False):
        world = new_world(mode=mode, bare=bare)
        self.assertTrue(has_arc(world), "authored parish-school arc required")
        return world


    @requires_arc
    def test_three_full_policies_pay_actual_registry_and_wages_without_parish_funds(self):
        for mode, total in ((1,2000),(2,1000),(3,2500)):
            with self.subTest(mode=mode):
                world = self._world(mode)
                original = world_facts(world)
                arc = ready_for_review(world, mode=mode)
                self.assertEqual(world.countries["NMG"][P+"mode"],mode)
                month(world,arc,6)
                finish_review(world,arc)
                self.assertEqual(world.treasury["NMG"],-total)
                self.assertEqual(world.countries["NMG"][P+"outcome"],1)
                self.assertEqual(world_facts(world),original)
                self.assertTrue(all(world.history["NMG"][jid]=="complete" for jid in JES))


    @requires_arc
    def test_finite_classroom_under_any_regime_finishes_without_schools_or_university(self):
        for laws in (("law_monarchy","law_autocracy","law_state_religion","law_no_schools"),
                     ("law_parliamentary_republic","law_universal_suffrage","law_total_separation","law_no_schools")):
            with self.subTest(laws=laws):
                countries=literal_countries(bare=True)
                countries["NMG"]["laws"]=list(laws)
                world=new_world(countries)
                original=world_facts(world)
                arc=ready_for_review(world,limited=True)
                self.assertEqual(world.countries["NMG"][P+"target"],2)
                month(world,arc,6)
                finish_review(world,arc,outcome=2)
                self.assertEqual(world.countries["NMG"][P+"outcome"],2)
                self.assertEqual(world.treasury["NMG"],-1000)
                self.assertEqual(world_facts(world),original)


    @requires_arc
    def test_two_exact_fees_respect_the_plan_fee_boundaries(self):
        # Both real bills: full 1/2/3 plus finite, including genuinely earned
        # old3 whose current full contract remains eligible before finite choice.
        scenarios = ((1, False, None, 1, 1), (2, False, None, .5, .5),
                     (3, False, None, 1, 1.5), (2, True, None, .5, .5),
                     (1, True, 3, .5, .5))
        for mode, limited, previous, register, wages in scenarios:
            for gross, base in ((52000, 1000), (0, 100)):
                with self.subTest(mode=mode, limited=limited, previous=previous, gross=gross):
                    world = (old_office_world(previous, academics_occupancy=.8)
                             if previous is not None else self._world(mode, bare=limited))
                    world.countries["NMG"]["yearly_gross_income"] = gross
                    arc = ready_for_review(world, mode=mode, limited=limited, number_through=1110)
                    for number, key, fee in ((1111, "pay_register", register * base),
                                             (1114, "pay_wages", wages * base)):
                        if number == 1114:
                            teacher = ("local_instructor" if limited else
                                       "appoint_clergy" if mode == 2 else "hire_academic")
                            play(world, arc, 1112, teacher)
                            play(world, arc, 1113, "sign_curriculum")
                        event = deliver(world, arc, number)
                        set_cash(world, fee - 1)
                        self.assertFalse(option_legal(world, event, key))
                        before = copy.deepcopy((world.countries, world.treasury,
                                                world.active, world.history))
                        force_option(world, event, key)
                        self.assertEqual((world.countries, world.treasury,
                                          world.active, world.history), before)
                        set_cash(world, fee)
                        self.assertTrue(option_legal(world, event, key))
                        before = world.treasury["NMG"]
                        choose(world, arc, event, key)
                        self.assertEqual(world.treasury["NMG"] - before, -fee)
                        self.assertEqual(cash(world), 0)
                        before = copy.deepcopy((world.countries, world.treasury,
                                                world.active, world.history))
                        self.assertFalse(option_legal(world, event, key))
                        force_option(world, event, key)
                        self.assertEqual((world.countries, world.treasury,
                                          world.active, world.history), before)

        for number, action, through in ((1111, "pay_register", 1110),
                                         (1114, "pay_wages", 1113)):
            for loss in ("law", "group", "teacher"):
                with self.subTest(unpaid_stage=number, current_loss=loss):
                    world = self._world()
                    arc = ready_for_review(world, number_through=through)
                    event = deliver(world, arc, number)
                    state = world.countries["NMG"]
                    self.assertTrue(option_legal(world, event, action))
                    if loss == "law":
                        state["laws"].remove("law_public_schools")
                    elif loss == "group":
                        for kind in ("ig_intelligentsia", "ig_petty_bourgeoisie"):
                            group(world, kind)["in_government"] = False
                    else:
                        employed_pop(world, "academics")["employed"] = False
                    self.assertFalse(option_legal(world, event, action))
                    before = copy.deepcopy((world.countries, world.treasury,
                                            world.active, world.history))
                    force_option(world, event, action)
                    self.assertEqual((world.countries, world.treasury,
                                      world.active, world.history), before)


    @requires_arc
    def test_missing_or_zero_mode_and_target_are_rejected_not_finite(self):
        for limited in (False, True):
            for name in ("mode", "target"):
                for bad in (None, 0, 99):
                    with self.subTest(limited=limited, name=name, bad=bad):
                        world = self._world(bare=limited)
                        arc = ready_for_review(world, limited=limited, number_through=1110)
                        event = deliver(world, arc, 1111)
                        state = world.countries["NMG"]
                        if bad is None:
                            del state[P + name]
                        else:
                            state[P + name] = bad
                        self.assertFalse(option_legal(world, event, "pay_register"))
                        before = copy.deepcopy((world.countries, world.treasury))
                        force_option(world, event, "pay_register")
                        self.assertEqual((world.countries, world.treasury), before)


    @requires_arc
    def test_same_current_facts_expose_two_node_old_3_vs_2_vs_absence_registry_difference(self):
        worlds = [old_office_world(previous) for previous in (3, 2, None)]
        self.assertEqual(world_facts(worlds[0]), world_facts(worlds[1]))
        self.assertEqual(world_facts(worlds[0]), world_facts(worlds[2]))
        self.assertTrue(all(cash(world) == 100000 for world in worlds))
        for previous, world, charge in zip((3, 2, None), worlds, (500, 1000, 1000)):
            arc = school_arc(world.cat)
            play(world, arc, 1110, MODES[1])
            before = cash(world)
            play(world, arc, 1111, "pay_register")
            self.assertEqual(before - cash(world), charge)
            teacher = deliver(world, arc, 1112)
            self.assertEqual(option_legal(world, teacher, "reuse_bilingual_roster"), previous == 3)
            self.assertFalse(option_legal(world, teacher, "hire_academic"))
            if previous == 3:
                choose(world, arc, teacher, "reuse_bilingual_roster")
            else:
                university(world)["occupancy"] = .8
                choose(world, arc, teacher, "hire_academic")
            signature = deliver(world, arc, 1113)
            university(world)["occupancy"] = .5
            self.assertEqual(option_legal(world, signature, "sign_curriculum"), previous == 3)
            if previous != 3:
                university(world)["occupancy"] = .8
            choose(world, arc, signature, "sign_curriculum")
            play(world, arc, 1114, "pay_wages")
            play(world, arc, 1115, "audit_teaching_duties")
            month(world, arc, 6)
            finish_review(world, arc)
            self.assertEqual(world.countries["NMG"][P + "outcome"], 1)


    @requires_arc
    def test_earned_old_contract_does_not_override_current_qualification_negative(self):
        world = old_office_world(3, academics_occupancy=.8)
        state = world.countries["NMG"]
        del state["ywc_nmg_office_six_months_complete"]
        self.assertEqual(state[OLD_PREFIX + "outcome"], 3)
        self.assertEqual(state["ywc_nmg_office_fee_paid"], 1)
        arc = ready_for_review(world, number_through=1110)
        before = cash(world)
        play(world, arc, 1111, "pay_register")
        self.assertEqual(before - cash(world), 1000)
        teacher = deliver(world, arc, 1112)
        self.assertFalse(option_legal(world, teacher, "reuse_bilingual_roster"))
        self.assertTrue(option_legal(world, teacher, "hire_academic"))

        # Once actually adopted, the earned source contract remains a live
        # obligation at both signature and teaching-duty acceptance. No refund
        # or automatic conversion to a fresh academic appointment is allowed.
        for number, action in ((1113, "sign_curriculum"),
                               (1115, "audit_teaching_duties")):
            for loss in ("earned_component", "current_office", "schools", "literacy"):
                with self.subTest(number=number, loss=loss):
                    world = old_office_world(3)
                    arc = ready_for_review(world, teacher="reuse_bilingual_roster",
                                           number_through=number - 1)
                    event = deliver(world, arc, number)
                    state = world.countries["NMG"]
                    self.assertTrue(option_legal(world, event, action))
                    paid_cash = cash(world)
                    if loss == "earned_component":
                        del state["ywc_nmg_office_six_months_complete"]
                    elif loss == "current_office":
                        office(world)["occupancy"] = .79
                    elif loss == "schools":
                        state["institutions"]["institution_schools"] = 0
                    else:
                        state["literacy_rate"] = .39
                    self.assertEqual(state[OLD_PREFIX + "outcome"], 3)
                    self.assertFalse(option_legal(world, event, action))
                    before = copy.deepcopy((world.countries, world.treasury,
                                            world.active, world.history))
                    force_option(world, event, action)
                    self.assertEqual((world.countries, world.treasury,
                                      world.active, world.history), before)
                    self.assertEqual(cash(world), paid_cash)


    @requires_arc
    def test_employee_investment_law_and_same_group_losses_are_negative_controls(self):
        for loss in ("unemployed","workplace","schools","law","government","clout","approval","split_group","war"):
            with self.subTest(loss=loss):
                world=self._world()
                arc=ready_for_review(world,number_through=1112)
                event=deliver(world,arc,1113)
                state=world.countries["NMG"]
                self.assertTrue(option_legal(world,event,"sign_curriculum"))
                if loss=="unemployed": employed_pop(world,"academics")["employed"]=False
                elif loss=="workplace": employed_pop(world,"academics")["workplace"]=office(world)
                elif loss=="schools": state["institutions"]["institution_schools"]=0
                elif loss=="law": state["laws"].remove("law_public_schools")
                elif loss=="war": state["is_at_war"]=True
                elif loss=="split_group":
                    group(world,"ig_intelligentsia")["clout"] = .09
                    group(world,"ig_petty_bourgeoisie")["in_government"] = False
                else:
                    for kind in ("ig_intelligentsia","ig_petty_bourgeoisie"):
                        group(world,kind)[{"government":"in_government","clout":"clout","approval":"approval"}[loss]]={"government":False,"clout":.09,"approval":-1}[loss]
                self.assertFalse(option_legal(world,event,"sign_curriculum"))
                before=copy.deepcopy((world.countries,world.treasury,world.active,world.history))
                force_option(world,event,"sign_curriculum")
                self.assertEqual((world.countries,world.treasury,world.active,world.history),before)

        for number, action in ((1113, "sign_curriculum"),
                               (1115, "audit_teaching_duties")):
            for tamper in ("mode", "target", "pilot"):
                with self.subTest(adopted_stage=number, contract_tamper=tamper):
                    countries = literal_countries()
                    alternate = copy.deepcopy(countries["NMG"]["states"][0])
                    alternate["region"] = "s:STATE_CALIFORNIA"
                    countries["NMG"]["states"].append(alternate)
                    world = new_world(countries)
                    arc = ready_for_review(world, number_through=number - 1)
                    event = deliver(world, arc, number)
                    state = world.countries["NMG"]
                    self.assertTrue(option_legal(world, event, action))
                    # These deliberately invalidate an already adopted contract;
                    # they never fill in a missing snapshot or advance a stage.
                    if tamper == "mode":
                        state[P + "mode"] = 2
                        state["laws"].remove("law_public_schools")
                        state["laws"].append("law_religious_schools")
                    elif tamper == "target":
                        state[P + "target"] = 2
                    else:
                        state[P + "pilot"] = StateRef(state["states"][1]["_sid"])
                    self.assertFalse(option_legal(world, event, action))
                    before = copy.deepcopy((world.countries, world.treasury,
                                            world.active, world.history))
                    force_option(world, event, action)
                    self.assertEqual((world.countries, world.treasury,
                                      world.active, world.history), before)


    @requires_arc
    def test_teacher_kind_follows_mode_and_current_profession_threshold(self):
        for mode, teacher, profession, boundary in ((1,"hire_academic","academics",.8),
                (2,"appoint_clergy","clergymen",.5),(3,"hire_academic","academics",.8)):
            with self.subTest(mode=mode):
                world = self._world(mode)
                arc = ready_for_review(world, mode=mode, number_through=1111)
                event = deliver(world, arc, 1112)
                self.assertTrue(option_legal(world, event, teacher))
                employed_pop(world, profession)["workplace"]["occupancy"] = boundary - .01
                self.assertFalse(option_legal(world, event, teacher))
                employed_pop(world, profession)["workplace"]["occupancy"] = boundary
                choose(world, arc, event, teacher)
                play(world, arc, 1113, "sign_curriculum")


    @requires_arc
    def test_creation_day_duplicate_and_five_six_month_observation(self):
        world = self._world()
        arc = ready_for_review(world)
        state = world.countries["NMG"]
        self.assertEqual(state[P + "review_streak"], 0)
        for _ in range(3):
            world.pulse(arc)
        self.assertEqual(state[P + "review_streak"], 0)
        for count in range(1, 6):
            month(world, arc)
            self.assertEqual(state[P + "review_streak"], count)
            for _ in range(3):
                world.pulse(arc)
            self.assertEqual(state[P + "review_streak"], count)
            self.assertNotIn(P + "review_mature", state)
        month(world, arc)
        self.assertEqual(state[P + "review_streak"], 6)
        self.assertEqual(state[P + "review_mature"], 1)

    @requires_arc
    def test_war_default_supply_loss_interrupts_and_explicit_restart_counts_six_fresh(self):
        for loss in ("war", "default", "supply"):
            with self.subTest(loss=loss):
                world = self._world()
                arc = ready_for_review(world)
                state = world.countries["NMG"]
                month(world, arc, 3)
                if loss == "war":
                    state["is_at_war"] = True
                elif loss == "default":
                    state["in_default"] = True
                else:
                    employed_pop(world, "academics")["employed"] = False
                month(world, arc)
                self.assertEqual(state[P + "review_streak"], 0)
                self.assertNotIn(P + "review_mature", state)
                self.assertEqual(state[P + "review_interrupted"], 1)
                state["is_at_war"] = state["in_default"] = False
                employed_pop(world, "academics")["employed"] = True
                month(world, arc)
                self.assertEqual(state[P + "review_streak"], 0)
                restart = deliver(world, arc, EVENTS[6])
                self.assertTrue(option_legal(world, restart, "restart_review"))
                choose(world, arc, restart, "restart_review")
                month(world, arc, 5)
                self.assertNotIn(P + "review_mature", state)
                month(world, arc)
                self.assertEqual(state[P + "review_mature"], 1)

    @requires_arc
    def test_explicit_finite_kind4_resign_restarts_six_fresh_and_preserves_paid_fees(self):
        world = self._world()
        arc = ready_for_review(world)
        state = world.countries["NMG"]
        month(world, arc, 4)
        employed_pop(world, "academics")["employed"] = False
        month(world, arc)
        self.assertEqual(state[P + "review_interrupted"], 1)
        event = deliver(world, arc, EVENTS[6])
        paid = cash(world)
        self.assertTrue(option_legal(world, event, "narrow_and_recount"))
        choose(world, arc, event, "narrow_and_recount")
        self.assertEqual(state[P + "teacher_kind"], 4)
        self.assertEqual(state[P + "review_streak"], 0)
        self.assertEqual(cash(world), paid)
        self.assertEqual(world.treasury["NMG"], -2000)
        month(world, arc, 5)
        self.assertNotIn(P + "review_mature", state)
        month(world, arc)
        self.assertEqual(state[P + "review_mature"], 1)

    @requires_arc
    def test_late_paid_setback_recovery_and_recount_keep_the_settled_bill(self):
        world = self._world()
        arc = ready_for_review(world)
        state = world.countries["NMG"]
        month(world, arc, 6)
        event = deliver(world, arc, 1116)
        self.assertFalse(option_legal(world, event, "request_setback"))
        state["is_at_war"] = True
        choose(world, arc, event, "request_setback")
        final = deliver(world, arc, 1117)
        state["is_at_war"] = False
        self.assertFalse(option_legal(world, final, "close_setback"))
        self.assertFalse(option_legal(world, final, "close_full"))
        before = copy.deepcopy((state, world.treasury))
        force_option(world, final, "close_setback")
        self.assertEqual((state, world.treasury), before)
        month(world, arc)
        self.assertEqual(state[P + "stage"], 1117)
        self.assertEqual(state[P + "review_streak"], 6)
        paid = cash(world)
        choose(world, arc, final, "recount")
        self.assertEqual(state[P + "review_streak"], 0)
        self.assertNotIn(P + "review_mature", state)
        month(world, arc, 6)
        finish_review(world, arc)
        self.assertEqual(state[P + "outcome"], 1)
        self.assertEqual(cash(world), paid)


    @requires_arc
    def test_recount_returns_to_six_fresh_without_recharging_and_cached_buttons_inert(self):
        world = self._world()
        arc = ready_for_review(world)
        month(world, arc, 6)
        play(world, arc, 1116, "request_full")
        state = world.countries["NMG"]
        settled = cash(world)
        event = deliver(world, arc, EVENTS[7])
        self.assertTrue(option_legal(world, event, "recount"))
        choose(world, arc, event, "recount")
        self.assertEqual(state[P + "review_streak"], 0)
        self.assertNotIn(P + "review_mature", state)
        self.assertEqual(cash(world), settled)
        # A recounted review matures again with six genuinely new months and
        # does not demand a fresh cash balance for the settled bills.
        month(world, arc, 5)
        self.assertNotIn(P + "review_mature", state)
        month(world, arc)
        self.assertEqual(state[P + "review_mature"], 1)
        played = [play(world, arc, 1116, "request_full"),
                  play(world, arc, 1117, "close_full")]
        self.assertEqual(state[P + "outcome"], 1)
        self.assertEqual(cash(world), settled)
        before = copy.deepcopy((state, world.treasury, world.active, world.history))
        for event in played:
            for name, _, body in event:
                if name == "option":
                    key = field(body, "name").rsplit(".", 1)[-1]
                    self.assertFalse(option_legal(world, event, key))
                    force_option(world, event, key)
        self.assertEqual((state, world.treasury, world.active, world.history), before)

        # A paid flag alone never substitutes for either positive actual amount
        # at the request boundary, for full or explicitly finite agreements.
        for limited in (False, True):
            for bill in ("register_amount", "wage_amount"):
                for invalid in (None, 0):
                    with self.subTest(request_limited=limited, paid_bill=bill, invalid=invalid):
                        world = self._world(bare=limited)
                        arc = ready_for_review(world, limited=limited)
                        month(world, arc, 6)
                        event = deliver(world, arc, 1116)
                        action = "request_limited" if limited else "request_full"
                        self.assertTrue(option_legal(world, event, action))
                        state = world.countries["NMG"]
                        if invalid is None:
                            del state[P + bill]
                        else:
                            state[P + bill] = invalid
                        self.assertFalse(option_legal(world, event, action))
                        before = copy.deepcopy((state, world.treasury,
                                                world.active, world.history))
                        force_option(world, event, action)
                        self.assertEqual((state, world.treasury,
                                          world.active, world.history), before)

    @requires_arc
    def test_signed_je_handoff_survives_owner_loss_without_new_capacity_and_releases_once(self):
        world = self._world()
        arc = ready_for_review(world, number_through=1112)
        event = deliver(world, arc, 1113)
        self.assertTrue(option_legal(world, event, "sign_curriculum"))
        force_option(world, event, "sign_curriculum")
        world.countries["NMG"]["states"][0]["owner"] = "MEX"
        world.refresh(arc)
        state = world.countries["NMG"]
        self.assertEqual(state[P + "phase"], 2)
        self.assertEqual(world.history["NMG"][JE1], "complete")
        self.assertIn(JE2, world.active["NMG"])
        event = deliver(world, arc, 1114)
        self.assertFalse(option_legal(world, event, "pay_wages"))
        self.assertTrue(option_legal(world, event, "withdraw"))
        choose(world, arc, event, "withdraw")
        self.assertEqual(state[P + "outcome"], 4)
        self.assertEqual(world.history["NMG"][JE2], "failed")
        self.assertFalse(any(jid in world.active["NMG"] for jid in JES))


    @requires_arc
    def test_every_originating_stage_withdraw_and_stale_receipt_do_not_mutate(self):
        for number in range(1110,1118):
            for defect in ("valid", "receipt_zero","phase_zero","phase_missing"):
                with self.subTest(stage=number,defect=defect):
                    world=self._world()
                    arc=school_arc(world.cat)
                    for earlier in range(1110,number):
                        if earlier==1116: month(world,arc,6)
                        play(world,arc,earlier,ACTIONS[earlier])
                    event=deliver(world,arc,number)
                    state=world.countries["NMG"]
                    self.assertTrue(option_legal(world,event,"withdraw"))
                    if defect=="valid":
                        choose(world,arc,event,"withdraw")
                        self.assertEqual(state[P+"outcome"],4)
                        self.assertEqual(state["ywc_v03_active_arc_count"],0)
                        before=copy.deepcopy((world.countries,world.treasury,world.active,world.history))
                        force_option(world,event,"withdraw")
                        self.assertEqual((world.countries,world.treasury,world.active,world.history),before)
                        continue
                    if defect=="receipt_zero": state[RECEIPT]=0
                    elif defect=="phase_zero": state[P+"phase"]=0
                    else: del state[P+"phase"]
                    self.assertFalse(option_legal(world,event,"withdraw"))
                    before=copy.deepcopy((world.countries,world.treasury,world.active,world.history))
                    force_option(world,event,"withdraw")
                    self.assertEqual((world.countries,world.treasury,world.active,world.history),before)


    @requires_arc
    def test_native_state_ref_pilot_loss_and_vanish_cannot_borrow_another_state(self):
        countries = literal_countries()
        alternate = copy.deepcopy(countries["NMG"]["states"][0])
        alternate["region"] = "s:STATE_CALIFORNIA"
        countries["NMG"]["states"].append(alternate)
        world = new_world(countries)
        arc = school_arc(world.cat)
        play(world, arc, 1110, ACTIONS[1110])
        state = world.countries["NMG"]
        pilot = state[P + "pilot"]
        self.assertIsInstance(pilot, StateRef)
        original = state["states"][0]
        original["owner"] = "MEX"
        event = deliver(world, arc, EVENTS[1])
        self.assertFalse(option_legal(world, event, ACTIONS[1111]))
        self.assertEqual(state[P + "pilot"], pilot)
        original["owner"] = "NMG"
        self.assertTrue(option_legal(world, event, ACTIONS[1111]))
        state["states"].remove(original)
        self.assertFalse(option_legal(world, event, ACTIONS[1111]))
        before = copy.deepcopy((state, world.treasury))
        force_option(world, event, ACTIONS[1111])
        self.assertEqual((state, world.treasury), before)
        self.assertEqual(state[P + "pilot"], pilot)

        # Presence/ownership of the saved pilot alone is insufficient: current
        # employees must work in that exact pilot, even if another owned state
        # has otherwise qualifying staff. Only a current employment fact is lost.
        countries = literal_countries()
        alternate = copy.deepcopy(countries["NMG"]["states"][0])
        alternate["region"] = "s:STATE_CALIFORNIA"
        countries["NMG"]["states"].append(alternate)
        world = new_world(countries)
        arc = ready_for_review(world, number_through=1112)
        event = deliver(world, arc, 1113)
        state = world.countries["NMG"]
        pilot = state[P + "pilot"]
        self.assertTrue(option_legal(world, event, "sign_curriculum"))
        for pop in state["states"][0]["pops"]:
            pop["employed"] = False
        self.assertEqual(state[P + "pilot"], pilot)
        self.assertFalse(option_legal(world, event, "sign_curriculum"))
        before = copy.deepcopy((state, world.treasury, world.active, world.history))
        force_option(world, event, "sign_curriculum")
        self.assertEqual((state, world.treasury, world.active, world.history), before)

    @requires_arc
    def test_handoff_does_not_demand_new_capacity_and_terminal_release_is_exactly_once(self):
        world = old_office_world(3, academics_occupancy=.8)
        arc = ready_for_review(world)
        state = world.countries["NMG"]
        self.assertEqual((state["ywc_v03_active_arc_count"],state["ywc_v03_visible_task_count"]),(1,1))
        month(world, arc, 6)
        play(world, arc, 1116, "request_full")
        final = deliver(world, arc, 1117)
        land = next(a for a in world.cat["arcs"] if a["slug"] == "v03_nmg_land_arbitration")
        world.refresh(land)
        unrelated = {k:copy.deepcopy(v) for k,v in state.items() if k.startswith("ywc_nmg_land_") and "pending" in k}
        self.assertTrue(unrelated, "control needs a genuine unrelated native pending queue")
        self.assertEqual(state["ywc_v03_active_arc_count"], 2)
        choose(world, arc, final, "close_full")
        self.assertEqual(state["ywc_v03_active_arc_count"], 1)
        self.assertEqual({k:state[k] for k in unrelated}, unrelated)
        before = copy.deepcopy((state,world.treasury,world.active,world.history))
        for key in ("close_full","withdraw","recount"):
            force_option(world, final, key)
        self.assertEqual((state,world.treasury,world.active,world.history),before)


    @requires_arc
    def test_narrowing_keeps_real_paid_fees_without_refund_or_duplicate_charge(self):
        world=self._world(3)
        arc=ready_for_review(world,mode=3)
        self.assertEqual(world.treasury["NMG"],-2500)
        month(world,arc,4)
        employed_pop(world,"academics")["employed"]=False
        month(world,arc)
        event=deliver(world,arc,1116)
        before=cash(world)
        choose(world,arc,event,"narrow_and_recount")
        month(world,arc,6)
        finish_review(world,arc,outcome=2)
        self.assertEqual(world.countries["NMG"][P+"outcome"],2)
        self.assertEqual(cash(world),before)
        self.assertEqual(world.treasury["NMG"],-2500)


if __name__ == "__main__":
    unittest.main()
