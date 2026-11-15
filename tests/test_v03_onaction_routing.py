"""Vanilla hooks must append named actions instead of replacing effect blocks."""
import tempfile
import unittest
from collections import defaultdict
from pathlib import Path

from clausewitz_harness import PulseWorld, parse
from tools.ywc_check import _on_action_hook_diagnostics, find_duplicate_keys


ROOT = Path(__file__).resolve().parents[1]
HOOK_CHILDREN = {
    "on_monthly_pulse_country": {
        "ywc_v03_shu_accounts_monthly", "ywc_v03_kor_accounts_monthly",
        "ywc_v03_jhg_accounts_monthly", "ywc_v03_nqg_accounts_monthly",
        "ywc_v03_nmg_accounts_monthly",
    },
    "on_become_subject": {"ywc_v03_jhg_became_subject", "ywc_v03_nqg_became_subject", "ywc_v03_nmg_became_subject"},
    "on_become_independent": {"ywc_v03_jhg_became_independent", "ywc_v03_nmg_became_independent"},
    "on_game_started_after_lobby": {"ywc_v03_initialize_after_lobby"},
}


def project_actions():
    declarations = defaultdict(list)
    for path in sorted((ROOT / "yongchang_world/common/on_actions").glob("*.txt")):
        for key, _, body in parse(path.read_text(encoding="utf-8-sig")):
            declarations[key].append((path, body))
    return declarations


class OnActionRoutingTests(unittest.TestCase):
    def test_all_owned_hooks_append_exact_named_children_without_effect_collision(self):
        declarations = project_actions()
        for hook, expected in HOOK_CHILDREN.items():
            with self.subTest(hook=hook):
                children = []
                for _, body in declarations[hook]:
                    self.assertFalse(any(k in ("effect", "trigger") for k, _, _ in body), hook)
                    for key, _, entries in body:
                        if key == "on_actions":
                            children.extend(name for name, _, _ in entries)
                for child in expected:
                    self.assertEqual(children.count(child), 1, child)
                    self.assertEqual(len(declarations[child]), 1, child)
                    self.assertEqual(sum(key == "effect" for key, _, _ in declarations[child][0][1]), 1, child)

    def test_each_owned_child_retains_its_authored_effects(self):
        expected = {
            "ywc_v03_shu_accounts_monthly": ("ywc_shu_collect_merchant_repayment",),
            "ywc_v03_kor_accounts_monthly": ("ywc_kor_pay_selected_contracts", "ywc_kor_instructor_monthly", "ywc_kor_procurement_monthly"),
            "ywc_v03_jhg_accounts_monthly": ("ywc_jhg_escort_monthly", "ywc_jhg_share_monthly"),
            "ywc_v03_nqg_accounts_monthly": ("ywc_nqg_aid_monthly", "ywc_nqg_port_treaty_monthly"),
            "ywc_v03_nmg_accounts_monthly": ("ywc_nmg_mexshare_monthly", "ywc_nmg_jointproject_monthly", "ywc_nmg_jointproject_provider_monthly"),
            "ywc_v03_jhg_became_subject": ("ywc_jhg_escort_cancel_unsigned", "ywc_jhg_share_cancel_unsigned"),
            "ywc_v03_jhg_became_independent": ("ywc_jhg_escort_cancel_unsigned", "ywc_jhg_share_cancel_unsigned"),
            "ywc_v03_nqg_became_subject": ("ywc_nqg_aid_cancel_unsigned", "ywc_nqg_port_treaty_cancel_unsigned"),
            "ywc_v03_nmg_became_subject": ("ywc_nmg_mexshare_cancel_unsigned", "ywc_nmg_jointproject_cancel_unsigned"),
            "ywc_v03_nmg_became_independent": ("ywc_nmg_mexshare_cancel_unsigned", "ywc_nmg_jointproject_cancel_unsigned"),
            "ywc_v03_initialize_after_lobby": ("ywc_v03_initialize_country",),
        }
        declarations = project_actions()
        def keys(body):
            for name, _, value in body:
                yield name
                if isinstance(value, list):
                    yield from keys(value)
        for action, effects in expected.items():
            with self.subTest(action=action):
                names = list(keys(declarations[action][0][1]))
                for effect in effects:
                    self.assertEqual(names.count(effect), 1, effect)

    def test_static_checker_rejects_both_vanilla_and_mod_effect_collisions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); mod = root / "mod"; game = root / "game"
            for path in (mod / "common/on_actions", game / "common/on_actions"):
                path.mkdir(parents=True)
            (game / "common/on_actions/vanilla.txt").write_text("on_monthly_pulse_country = { effect = { always = yes } }\n", encoding="utf-8")
            (mod / "common/on_actions/a.txt").write_text("on_monthly_pulse_country = { effect = { always = yes } }\nywc_child = { effect = { always = yes } }\n", encoding="utf-8")
            (mod / "common/on_actions/b.txt").write_text("ywc_child = { effect = { always = yes } }\n", encoding="utf-8")
            diagnostics = _on_action_hook_diagnostics(mod, game)
            self.assertTrue(any("on_monthly_pulse_country" in row and "effect" in row and "conflict" in row for row in diagnostics), diagnostics)
            self.assertTrue(any("ywc_child" in row and "effect" in row and "conflict" in row for row in diagnostics), diagnostics)

    def test_static_checker_accepts_multiple_append_lists_without_replacing_vanilla(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); mod = root / "mod"; game = root / "game"
            for path in (mod / "common/on_actions", game / "common/on_actions"):
                path.mkdir(parents=True)
            (game / "common/on_actions/vanilla.txt").write_text("on_monthly_pulse_country = { effect = { always = yes } }\n", encoding="utf-8")
            (mod / "common/on_actions/a.txt").write_text("on_monthly_pulse_country = { on_actions = { ywc_one } }\nywc_one = { effect = { always = yes } }\n", encoding="utf-8")
            (mod / "common/on_actions/b.txt").write_text("# effect = { ignored }\non_monthly_pulse_country = { on_actions = { ywc_two } }\nywc_two = { effect = { always = yes } }\n", encoding="utf-8")
            self.assertEqual(_on_action_hook_diagnostics(mod, game), [])

    def test_static_checker_accepts_repeated_appended_children(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); mod = root / "mod"; game = root / "game"
            for path in (mod / "common/on_actions", game / "common/on_actions"):
                path.mkdir(parents=True)
            (game / "common/on_actions/vanilla.txt").write_text("on_monthly_pulse_country = { effect = { always = yes } }\n", encoding="utf-8")
            (mod / "common/on_actions/a.txt").write_text("on_monthly_pulse_country = { on_actions = { ywc_one } }\nywc_one = { effect = { always = yes } }\n", encoding="utf-8")
            (mod / "common/on_actions/b.txt").write_text("on_monthly_pulse_country = { on_actions = { ywc_one } }\n", encoding="utf-8")
            self.assertEqual(_on_action_hook_diagnostics(mod, game), [])

    def test_generic_duplicate_check_allows_additive_on_action_declarations_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            actions = root / "common/on_actions"
            effects = root / "common/scripted_effects"
            actions.mkdir(parents=True); effects.mkdir(parents=True)
            (actions / "a.txt").write_text("ywc_parent = { effect = {} }\n", encoding="utf-8")
            (actions / "b.txt").write_text("ywc_parent = { on_actions = { ywc_child } }\n", encoding="utf-8")
            (effects / "a.txt").write_text("ywc_duplicate = {}\n", encoding="utf-8")
            (effects / "b.txt").write_text("ywc_duplicate = {}\n", encoding="utf-8")
            self.assertEqual(find_duplicate_keys(root), {"ywc_duplicate"})

    def test_mod_singleton_conflicts_are_checked_without_a_game_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); actions = root / "common/on_actions"
            actions.mkdir(parents=True)
            (actions / "a.txt").write_text("ywc_child = { effect = {} }\n", encoding="utf-8")
            (actions / "b.txt").write_text("ywc_child = { effect = {} }\n", encoding="utf-8")
            diagnostics = _on_action_hook_diagnostics(root, None)
            self.assertTrue(any("ywc_child" in row and "effect" in row and "conflict" in row for row in diagnostics), diagnostics)

    def test_checker_ignores_nested_effect_names_and_commented_action_lists(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); mod = root / "mod"; game = root / "game"
            for path in (mod / "common/on_actions", game / "common/on_actions"):
                path.mkdir(parents=True)
            (game / "common/on_actions/vanilla.txt").write_text("on_monthly_pulse_country = { effect = {} }\n", encoding="utf-8")
            (mod / "common/on_actions/a.txt").write_text(
                "# on_actions = { ghost_child }\non_monthly_pulse_country = { on_actions = { ywc_one } }\n"
                "ywc_one = { effect = {\n ywc_valid_scripted_effect = { always = yes }\n} }\n", encoding="utf-8")
            self.assertEqual(_on_action_hook_diagnostics(mod, game), [])

    def test_nested_vanilla_effect_is_not_mistaken_for_a_code_hook(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); mod = root / "mod"; game = root / "game"
            for path in (mod / "common/on_actions", game / "common/on_actions"):
                path.mkdir(parents=True)
            (game / "common/on_actions/vanilla.txt").write_text("on_monthly_pulse_country = { effect = {\n fake_hook = { always = yes }\n} }\n", encoding="utf-8")
            (mod / "common/on_actions/a.txt").write_text("fake_hook = { on_actions = { ywc_one } }\nywc_one = { effect = {} }\n", encoding="utf-8")
            diagnostics = _on_action_hook_diagnostics(mod, game)
            self.assertTrue(any("fake_hook" in row and "neither a vanilla hook" in row for row in diagnostics), diagnostics)

    def test_checker_recognizes_direct_trigger_event_but_not_comments_or_nested_parameters(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); mod = root / "mod"; game = root / "game"
            for path in (mod / "common/on_actions", mod / "events", game / "common/on_actions"):
                path.mkdir(parents=True)
            (game / "common/on_actions/vanilla.txt").write_text("on_monthly_pulse_country = { effect = {} }\n", encoding="utf-8")
            (mod / "common/on_actions/a.txt").write_text(
                "ywc_direct = { effect = {} }\nywc_commented = { effect = {} }\nywc_nested = { effect = {} }\n", encoding="utf-8")
            (mod / "events/a.txt").write_text(
                "# trigger_event = { on_action = ywc_commented }\n"
                "effect = { trigger_event = { on_action = ywc_direct days = 1 other = { on_action = ywc_nested } } }\n", encoding="utf-8")
            diagnostics = _on_action_hook_diagnostics(mod, game)
            self.assertFalse(any("ywc_direct" in row for row in diagnostics), diagnostics)
            self.assertTrue(any("ywc_commented" in row for row in diagnostics), diagnostics)
            self.assertTrue(any("ywc_nested" in row for row in diagnostics), diagnostics)

    def test_checker_recognizes_random_first_valid_and_fallback_actions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); mod = root / "mod"; game = root / "game"
            for path in (mod / "common/on_actions", game / "common/on_actions"):
                path.mkdir(parents=True)
            (game / "common/on_actions/vanilla.txt").write_text("on_monthly_pulse_country = { effect = {} }\n", encoding="utf-8")
            (mod / "common/on_actions/a.txt").write_text(
                "on_monthly_pulse_country = { random_on_actions = { 100 = ywc_random 25 = 0 } "
                "first_valid_on_action = { ywc_first ywc_missing } fallback = ywc_fallback }\n"
                "ywc_random = { effect = {} }\nywc_first = { effect = {} }\nywc_fallback = { effect = {} }\n", encoding="utf-8")
            diagnostics = _on_action_hook_diagnostics(mod, game)
            self.assertEqual(len(diagnostics), 1, diagnostics)
            self.assertIn("ywc_missing", diagnostics[0])
            self.assertIn("not declared", diagnostics[0])

    def test_checker_skips_nested_delay_values_in_appended_action_lists(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); mod = root / "mod"; game = root / "game"
            for path in (mod / "common/on_actions", game / "common/on_actions"):
                path.mkdir(parents=True)
            (game / "common/on_actions/vanilla.txt").write_text("on_monthly_pulse_country = { effect = {} }\n", encoding="utf-8")
            (mod / "common/on_actions/a.txt").write_text(
                "on_monthly_pulse_country = { on_actions = { ywc_one delay = { days = normal_modifier_time } ywc_two } }\n"
                "ywc_one = { effect = {} }\nywc_two = { effect = {} }\n", encoding="utf-8")
            self.assertEqual(_on_action_hook_diagnostics(mod, game), [])

    def test_combined_graph_preserves_vanilla_and_executes_both_joint_project_owners(self):
        from test_v03_nmg_partner_response import NmgPartnerWorld, base_countries
        from test_v03_nmg_joint_response import accept_joint
        countries = base_countries(); world = NmgPartnerWorld(countries)
        directory = ROOT / "yongchang_world/common/on_actions"
        for name in ("ywc_v03_shu_accounts.txt", "ywc_v03_jhg_accounts.txt", "ywc_v03_nqg_accounts.txt"):
            world.merge_on_actions(parse((directory / name).read_text(encoding="utf-8-sig")))
        # Model the existing vanilla singleton alongside additive mod children.
        world.merge_on_actions(parse("on_monthly_pulse_country = { effect = { set_variable = { name = ywc_test_vanilla_pulse value = 1 } } }"))
        children = [name for key, _, body in world.on_actions["on_monthly_pulse_country"]
                    if key == "on_actions" for name, _, _ in body]
        self.assertEqual(set(children), HOOK_CHILDREN["on_monthly_pulse_country"])
        self.assertEqual(len(children), len(set(children)))
        accept_joint(world, "joint_jhg")
        world.run_country_monthly("NMG"); world.run_country_monthly("JHG")
        self.assertEqual(countries["NMG"]["ywc_test_vanilla_pulse"], 1)
        self.assertEqual(countries["JHG"]["ywc_test_vanilla_pulse"], 1)
        self.assertEqual(countries["NMG"]["ywc_nmg_jointproject_own_paid_total"], 10)
        self.assertEqual(countries["NMG"]["ywc_nmg_jointproject_partner_paid_total"], 10)
        self.assertEqual((world.treasury["NMG"], world.treasury["JHG"]), (-10, -10))

    def test_action_effects_cannot_leak_saved_scopes_to_child_or_sibling(self):
        from test_v03_nmg_partner_response import NmgPartnerWorld, base_countries
        countries = base_countries(); world = NmgPartnerWorld(countries)
        world.merge_on_actions(parse("""
            ywc_test_parent = {
              effect = { save_scope_as = ywc_test_parent_private }
              on_actions = { ywc_test_first ywc_test_second }
            }
            ywc_test_first = { effect = { save_scope_as = ywc_test_sibling_private } }
            ywc_test_second = { effect = {
              if = { limit = { exists = scope:ywc_test_parent_private } set_variable = { name = ywc_test_parent_leak value = 1 } }
              if = { limit = { exists = scope:ywc_test_sibling_private } set_variable = { name = ywc_test_sibling_leak value = 1 } }
            } }
        """))
        world.run_on_action("ywc_test_parent", "NMG")
        self.assertNotIn("ywc_test_parent_leak", countries["NMG"])
        self.assertNotIn("ywc_test_sibling_leak", countries["NMG"])

    def test_no_root_startup_dispatch_initializes_only_the_ten_authored_countries(self):
        tags = ("SHU", "DMG", "KOR", "JHG", "LAN", "NMG", "NQG", "OIR", "MGL", "TIB")
        class StartupWorld(PulseWorld):
            def __init__(self):
                effects = (ROOT / "yongchang_world/common/scripted_effects/ywc_v03_effects.txt").read_text(encoding="utf-8-sig")
                super().__init__(effects, {tag: {} for tag in (*tags, "FRA")})
                self.initializations = defaultdict(int)
            def run(self, name, tag="SHU"):
                if name == "ywc_v03_initialize_country":
                    self.initializations[tag] += 1
                return super().run(name, tag)

        world = StartupWorld()
        source = parse((ROOT / "yongchang_world/common/on_actions/ywc_v03_startup.txt").read_text(encoding="utf-8-sig"))
        graph = defaultdict(list)
        for name, _, body in source:
            graph[name].extend(body)
        # An independent vanilla singleton models preservation, not its actual contents.
        graph["on_game_started_after_lobby"].append(("effect", "=", parse(
            "every_country = { set_variable = { name = ywc_test_vanilla_startup value = 1 } }")))
        def dispatch(name, active=frozenset()):
            self.assertNotIn(name, active)
            for key, _, body in graph[name]:
                if key == "on_actions":
                    for child, _, _ in body:
                        dispatch(child, active | {name})
                elif key == "effect":
                    for effect, _, scope in body:
                        self.assertEqual(effect, "every_country", "the no-root subset must not invent a country root")
                        limits = [value for child, _, value in scope if child == "limit"]
                        self.assertLessEqual(len(limits), 1)
                        for tag in world.countries:
                            if not limits or world.conditions(limits[0], tag):
                                world.execute([node for node in scope if node[0] != "limit"], tag)
                else:
                    self.fail(f"unsupported startup on_action block {key}")
        dispatch("on_game_started_after_lobby")
        for tag in tags:
            self.assertEqual(world.initializations[tag], 1, tag)
            self.assertEqual(world.countries[tag]["ywc_v03_initialized"], 1, tag)
            self.assertEqual(world.countries[tag]["ywc_test_vanilla_startup"], 1, tag)
        self.assertNotIn("FRA", world.initializations)
        self.assertNotIn("ywc_v03_initialized", world.countries["FRA"])
        self.assertEqual(world.countries["FRA"]["ywc_test_vanilla_startup"], 1)


if __name__ == "__main__":
    unittest.main()
