import importlib.util
import io
import pathlib
import sys
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from tools.ownership_topology import audit_ownership_topology, component_sizes, main


ROOT = pathlib.Path(__file__).parents[1]
BASELINE_FILE = ROOT / "data/baseline/vic3-1.13.11.json"
OVERRIDES_FILE = ROOT / "data/scenario/ownership_overrides.json"
PROVINCES_MAP_FILE = pathlib.Path(
    r"E:/SteamLibrary/steamapps/common/Victoria 3/game/map_data/provinces.png"
)


def _map_audit_dependencies_missing() -> str | None:
    """The map audit needs Pillow and NumPy; report the missing one.

    A missing optional dependency is an environment gap, not a repository
    regression, so callers skip instead of failing the suite.
    """

    missing = [
        name
        for name in ("numpy", "PIL")
        if importlib.util.find_spec(name) is None
    ]
    if not missing:
        return None
    return "Pillow and NumPy are required for map topology audits: missing " + ", ".join(missing)


class OwnershipTopologyTest(unittest.TestCase):
    def test_component_sizes_reports_disconnected_province_groups(self):
        adjacency = {
            "a": {"b"},
            "b": {"a"},
            "c": set(),
        }
        self.assertEqual(component_sizes({"a", "b", "c"}, adjacency), [2, 1])

    def test_current_weak_groups_are_only_declared_island_topologies(self):
        dependency_error = _map_audit_dependencies_missing()
        if dependency_error is not None:
            self.skipTest(dependency_error)
        try:
            rows = audit_ownership_topology(
                BASELINE_FILE,
                OVERRIDES_FILE,
                PROVINCES_MAP_FILE,
            )
        except RuntimeError as error:
            self.skipTest(str(error))

        weak = {
            (row["state"], row["owner"])
            for row in rows
            if row["largest_component_ratio"] < 0.5
        }
        self.assertEqual(
            weak,
            {
                ("STATE_LUZON", "PHI"),
                ("STATE_WEST_MICRONESIA", "MHL"),
            },
        )
        weak_reasons = {
            (row["state"], row["owner"]): row.get("topology_exception")
            for row in rows
            if row["largest_component_ratio"] < 0.5
        }
        self.assertEqual(
            weak_reasons,
            {
                ("STATE_LUZON", "PHI"): "natural_archipelago",
                ("STATE_WEST_MICRONESIA", "MHL"): "natural_archipelago",
            },
        )

    def test_cli_prints_declared_exception_reason_for_weak_groups(self):
        dependency_error = _map_audit_dependencies_missing()
        if dependency_error is not None:
            self.skipTest(dependency_error)
        if not PROVINCES_MAP_FILE.is_file():
            self.skipTest(f"province map does not exist: {PROVINCES_MAP_FILE}")

        output = io.StringIO()
        argv = [
            "ownership_topology.py",
            "--baseline",
            str(BASELINE_FILE),
            "--overrides",
            str(OVERRIDES_FILE),
            "--provinces-map",
            str(PROVINCES_MAP_FILE),
            "--weak-only",
        ]
        with patch.object(sys, "argv", argv), redirect_stdout(output):
            self.assertEqual(main(), 0)

        lines = output.getvalue().splitlines()
        self.assertTrue(lines)
        self.assertTrue(all("exception=natural_archipelago" in line for line in lines))


if __name__ == "__main__":
    unittest.main()
