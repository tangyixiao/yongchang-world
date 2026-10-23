"""Strict actual-source world factory for the MGL inline transport tests.

This is a test-only registration seam. It reuses the accepted real history,
legacy-event, initializer and root-admission fixture, and adds only renderer
output to the temporary world registries before root JEs execute.
"""
from __future__ import annotations

import copy
from contextlib import contextmanager
from unittest.mock import patch

from tools import build_v03_content
from tests.clausewitz_harness import parse
from tests import test_v03_mgl_actual_source as source_fixture
from tests.test_v03_mgl_inline_adapter import _v2_catalog_from_formal_mgl_source
from tools.v03_inline_delivery_adapter import render_inline_country_adapters, validate_inline_catalog


class InlineFeatureUnavailable(RuntimeError):
    """The ordinary feature RED: MGL metadata/API support is not registered."""


def _render_registered_candidate():
    candidate = _v2_catalog_from_formal_mgl_source()
    validate_inline_catalog(candidate)
    adapter = render_inline_country_adapters(candidate)
    return candidate, adapter


def assert_inline_supported(testcase):
    """Assert public API support, keeping parse/source faults distinguishable."""
    try:
        _, rendered = _render_registered_candidate()
    except ValueError as exc:
        # Current baseline lacks MGL support. The candidate is built from the
        # real source first; its failure is the intended contract RED.
        if "inline adapter is currently enabled only for registered inline countries" in str(exc):
            testcase.fail(f"MGL inline adapter feature is not registered: {exc}")
        raise
    if len(rendered.get("event_hooks", {})) != 24:
        testcase.fail("MGL renderer must guard all 24 native event bodies")
    return rendered


def _script_nodes(script):
    """Parse rendered Clausewitz definitions into the harness tuple shape."""
    definitions = {}
    for key, _, body in parse(script):
        if key in definitions:
            raise AssertionError(("duplicate_rendered_definition", key))
        definitions[key] = body
    return definitions


@contextmanager
def _registered_source_world(catalog, rendered):
    """Temporarily teach the old strict fixture to register renderer output.

    The seam installs only generated FX/TRG and generated journal/event
    wrappers. It does not replace native conditions, source effects, or facts.
    """
    original_class = source_fixture._StrictMglWorld

    class _InlineRegisteredWorld(original_class):
        def __init__(self, effects, triggers, countries):
            # Registries are private per world; append real generated helper
            # definitions to the actual authored registries before construction.
            effect_defs = _script_nodes(rendered["effects"]) if rendered is not None else {}
            trigger_defs = _script_nodes(rendered["triggers"]) if rendered is not None else {}
            existing_effect_defs = _script_nodes(effects)
            existing_trigger_defs = _script_nodes(triggers)
            for key in effect_defs:
                if key in existing_effect_defs:
                    raise AssertionError(("inline_effect_collision", key))
            for key in trigger_defs:
                if key in existing_trigger_defs:
                    raise AssertionError(("inline_trigger_collision", key))
            extra_effects = rendered["effects"] if rendered is not None else ""
            extra_triggers = rendered["triggers"] if rendered is not None else ""
            super().__init__(effects + "\n" + extra_effects,
                             triggers + "\n" + extra_triggers, countries)
            self._inline_rendered = rendered
            self._inline_catalog = catalog
            self._inline_installed = False

        def activate_journal(self, journal_id, tag=source_fixture.TAG):
            if not self._inline_installed:
                # Adapter journal_scripts are local source script blocks. Use
                # the actual content builder to add JE ids, witness writes,
                # goals and exit blocks to the generated journal definitions.
                adapter = self._inline_rendered
                journal_text = build_v03_content._render_journal_file(self._inline_catalog, adapter)
                generated_journals = _script_nodes(journal_text)
                for jid in (journal["id"] for arc in self._inline_catalog["arcs"]
                            for journal in arc["journals"]):
                    if jid not in generated_journals:
                        raise AssertionError(("generated_journal_script_missing", jid))
                    self.journal_defs[jid] = generated_journals[jid]

                # event_hooks are dispatch helper names used by the real event
                # renderer to guard trigger and immediate. They are not direct
                # immediate effects; ack_hooks and inline_proofs must remain
                # in their builder-authored positions after the native body.
                events_text = build_v03_content._render_event_file(
                    self._inline_catalog, source_fixture.ROOT, adapter)
                generated_events = _script_nodes(events_text)
                event_ids = (event["id"] for arc in self._inline_catalog["arcs"]
                             for event in arc["events"])
                for event_id in event_ids:
                    if event_id not in generated_events or event_id not in self.event_defs:
                        raise AssertionError(("generated_event_missing", event_id))
                    self.event_defs[event_id] = generated_events[event_id]
                self._inline_installed = True
            return super().activate_journal(journal_id, tag)

    with patch.object(source_fixture, "_StrictMglWorld", _InlineRegisteredWorld):
        yield


LAND_REFORM_LAWS = frozenset({"law_tenant_farmers", "law_serfdom", "law_homesteading"})


def validate_ordinary_facts(facts):
    """Require exactly one supported land reform law in positive source worlds."""
    selected = set(facts["laws"]) & LAND_REFORM_LAWS
    if len(selected) != 1:
        raise ValueError(("inconsistent_land_reform_laws", sorted(selected)))
    return facts


def legal_ordinary_facts(ordinary_facts=None):
    """Copy ordinary facts; the new default selects tenant farmers alone."""
    facts = copy.deepcopy(source_fixture._ordinary_facts() if ordinary_facts is None else ordinary_facts)
    if ordinary_facts is None:
        facts["laws"].difference_update(LAND_REFORM_LAWS)
        facts["laws"].add("law_tenant_farmers")
    return validate_ordinary_facts(facts)


def actual_mgl_inline_identity_control_world(admission_order=None, ordinary_facts=None):
    """Build normal source files through the production builder, with no adapter."""
    catalog = _v2_catalog_from_formal_mgl_source()
    with _registered_source_world(catalog, None):
        return source_fixture.actual_mgl_admission_world(admission_order, legal_ordinary_facts(ordinary_facts))


def actual_mgl_inline_world(admission_order=None, ordinary_facts=None):
    """Return a strict world with real renderer registrations and source history."""
    try:
        catalog, rendered = _render_registered_candidate()
    except ValueError as exc:
        if "inline adapter is currently enabled only for registered inline countries" in str(exc):
            raise InlineFeatureUnavailable(str(exc)) from exc
        raise
    with _registered_source_world(catalog, rendered):
        return source_fixture.actual_mgl_admission_world(admission_order, legal_ordinary_facts(ordinary_facts))


def pulse_inline_journals(world):
    return source_fixture.pulse_actual_journals(world)


def choose_inline_option(world, event_id, suffix):
    return source_fixture.choose_actual_option(world, event_id, suffix)


class MglInlineActualSourceFactoryControls(source_fixture.unittest.TestCase):
    def test_legal_ordinary_fact_controls_without_inline_feature(self):
        baseline = source_fixture._ordinary_facts()
        facts = legal_ordinary_facts()
        self.assertEqual(facts["laws"] & LAND_REFORM_LAWS, {"law_tenant_farmers"})
        self.assertEqual(baseline, source_fixture._ordinary_facts())
        self.assertIsNot(facts["states"], baseline["states"])
        for law in LAND_REFORM_LAWS:
            with self.subTest(law=law):
                candidate = copy.deepcopy(facts)
                candidate["laws"].difference_update(LAND_REFORM_LAWS)
                candidate["laws"].add(law)
                self.assertEqual(legal_ordinary_facts(candidate), candidate)
        for laws in (set(), LAND_REFORM_LAWS, {"law_tenant_farmers", "law_serfdom"}):
            with self.subTest(laws=laws):
                candidate = copy.deepcopy(facts)
                candidate["laws"].difference_update(LAND_REFORM_LAWS)
                candidate["laws"].update(laws)
                with self.assertRaises(ValueError):
                    legal_ordinary_facts(candidate)

    def test_native_source_factory_remains_a_separate_positive_control(self):
        world, evidence = source_fixture.actual_mgl_admission_world(ordinary_facts=legal_ordinary_facts())
        self.assertEqual(evidence["counts"], {"active": 3, "visible": 3})
        self.assertEqual(len(evidence["legacy_trace"]), 6)
        self.assertIs(world.strict_trigger_defs, world.trigger_defs)

    def test_real_builder_identity_registration_preserves_native_ast_and_pulse(self):
        baseline, _ = source_fixture.actual_mgl_admission_world(ordinary_facts=legal_ordinary_facts())
        rendered, _ = actual_mgl_inline_identity_control_world()
        self.assertEqual(rendered.journal_defs, baseline.journal_defs)
        self.assertEqual(rendered.event_defs, baseline.event_defs)
        self.assertEqual(rendered.effects, baseline.effects)
        self.assertEqual(rendered.trigger_defs, baseline.trigger_defs)
        self.assertEqual(pulse_inline_journals(rendered),
                         source_fixture.pulse_actual_journals(baseline))
        self.assertEqual(rendered.countries, baseline.countries)
        self.assertEqual(rendered.active_journals, baseline.active_journals)

    def test_identity_control_world_registries_are_private_per_instance(self):
        first, _ = actual_mgl_inline_identity_control_world()
        second, _ = actual_mgl_inline_identity_control_world()
        self.assertIsNot(first.effects, second.effects)
        self.assertIsNot(first.trigger_defs, second.trigger_defs)
        self.assertIsNot(first.journal_defs, second.journal_defs)
        self.assertIsNot(first.event_defs, second.event_defs)
        first.effects["__mgl_isolation_probe__"] = ("effect",)
        first.trigger_defs["__mgl_isolation_probe__"] = ("trigger",)
        try:
            self.assertNotIn("__mgl_isolation_probe__", second.effects)
            self.assertNotIn("__mgl_isolation_probe__", second.trigger_defs)
        finally:
            first.effects.pop("__mgl_isolation_probe__", None)
            first.trigger_defs.pop("__mgl_isolation_probe__", None)

    def test_new_api_has_stable_callable_surface(self):
        self.assertTrue(callable(actual_mgl_inline_world))
        self.assertTrue(callable(actual_mgl_inline_identity_control_world))
        self.assertTrue(callable(assert_inline_supported))
        self.assertTrue(callable(pulse_inline_journals))
        self.assertTrue(callable(choose_inline_option))
