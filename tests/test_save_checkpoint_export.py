"""Tests for the save-based checkpoint export.

The fixtures build a miniature save in the same shape the game writes (a
``<id>={...}`` entry per database row, closed by a brace at column zero), so the
parsing rules are exercised without a 100 MB real save.  The real 1.13.11 save in
``artifacts/observe/manual-gate23-1836-shu-01`` was used to confirm the same
readers against genuine output.
"""

import csv
import pathlib
import tempfile
import unittest

from tools.record_checkpoint import load_rows
from tools.save_checkpoint_export import (
    CORE_COUNTRIES,
    CSV_COLUMNS,
    SaveExportError,
    export,
    load_subject_actions,
    write_csv,
)


SUBJECT_TYPES = """
subject_type_tributary = {
    diplomatic_action = tributary
    autonomy_level = 3
}

subject_type_protectorate = {
    diplomatic_action = protectorate
    autonomy_level = 2
}

subject_type_vassal = {
    diplomatic_action = vassal
    autonomy_level = 1
}
"""

# country id -> tag, deliberately not in CORE_COUNTRIES order.
TAGS = {1: "JHG", 2: "SHU", 3: "DMG", 4: "NQG", 5: "OIR", 6: "MGL", 7: "TIB", 8: "KOR", 9: "LAN", 10: "NMG"}
RANKS = {
    1: "unrecognized_regional_power",
    2: "unrecognized_major_power",
    3: "unrecognized_regional_power",
    4: "unrecognized_power",
    5: "unrecognized_regional_power",
    6: "unrecognized_regional_power",
    7: "unrecognized_regional_power",
    8: "unrecognized_regional_power",
    9: "unrecognized_power",
    10: "unrecognized_power",
}
# Every country but SHU sits in its own market; SHU owns market 20 and KOR uses it.
MARKET_OWNER = {10: 1, 20: 2, 30: 3, 40: 4, 50: 5, 60: 6, 70: 7, 80: 8, 90: 9}
COUNTRY_MARKET = {1: 10, 2: 20, 3: 30, 4: 40, 5: 50, 6: 60, 7: 70, 8: 20, 9: 90, 10: 10}
# Population: lower + middle + upper strata, and the pops that must add up to it.
STRATA = {
    1: (100, 40, 10),
    2: (17000000, 300000, 70000),
    3: (900000, 500, 300),
    4: (45000, 100, 38),
    5: (840000, 2000, 500),
    6: (600000, 1500, 500),
    7: (3000000, 130000, 6000),
    8: (16000000, 270000, 4000),
    9: (46000, 100, 21),
    10: (45000, 20, 3),
}


def _tag_order(tag: str) -> int:
    return [value for _key, value in sorted(TAGS.items())].index(tag) + 1


def build_save(date: str = "1846.1.1", omit_country: str | None = None) -> str:
    """A save carrying the ten core countries in the real file's shape."""

    parts: list[str] = ["SAV0100deadbeef00000001\n"]
    parts.append(
        "meta_data={\n"
        '\tversion="1.13.11"\n'
        f"\tgame_date={date}\n"
        '\treal_date=126.9.20\n'
        '\tname="JHG"\n'
        '\tdlcs={ "Sphere of Influence" }\n'
        '\tmods={ "The Yongchang World" }\n'
        "}\n"
        "ironman={\n\tironman=no\n}\n"
        f"date={date}\n"
        "counters={\n\tcommand=1\n}\n"
    )

    country_rows = []
    for identifier, tag in TAGS.items():
        if tag == omit_country:
            continue
        lower, middle, upper = STRATA[identifier]
        country_rows.append(
            f"{identifier}={{\n"
            "\tis_main_tag=yes\n"
            f'\tdefinition="{tag}"\n'
            f"\tmarket={COUNTRY_MARKET[identifier]}\n"
            "\tpop_statistics={\n"
            f"\t\tpopulation_lower_strata={lower}\n"
            f"\t\tpopulation_middle_strata={middle}\n"
            f"\t\tpopulation_upper_strata={upper}\n"
            "\t}\n"
            "}\n"
        )
    parts.append("country_manager={\n\tdatabase={\n0=none\n" + "".join(country_rows) + "}\n}\n")

    state_rows = []
    pop_rows = []
    for identifier, tag in TAGS.items():
        if tag == omit_country:
            continue
        lower, middle, upper = STRATA[identifier]
        total = lower + middle + upper
        state_rows.append(f"{identifier}={{\n\tcountry={identifier}\n}}\n")
        pop_rows.append(
            f"{identifier}={{\n"
            "\ttype=laborers\n"
            f"\tworkforce={total - 5}\n"
            "\tdependents=5\n"
            f"\tlocation={identifier}\n"
            "}\n"
        )
    parts.append("states={\n\tdatabase={\n" + "".join(state_rows) + "}\n}\n")
    parts.append("pops={\n\tdatabase={\n0=none\n" + "".join(pop_rows) + "}\n}\n")

    ranking_rows = "".join(
        "{\n"
        f"\t\t\trank={RANKS[identifier]}\n"
        "\t\t\ttarget=minor_power\n"
        "\t\t\tprestige=1\n"
        "\t\t\tscore=1\n"
        f"\t\t\tcountry={identifier}\n"
        "\t\t}\n"
        for identifier in TAGS
        if TAGS[identifier] != omit_country
    )
    parts.append(
        "country_rankings={\n\taverage_prestige=1\n\tcountry_rankings={ " + ranking_rows + " }\n}\n"
    )

    market_rows = "".join(
        f"{market}={{\n\towner={owner}\n}}\n" for market, owner in MARKET_OWNER.items()
    )
    parts.append("market_manager={\n\tmarkets_counter=100\n\tworld_market={\n\t}\n\tdatabase={\n" + market_rows + "}\n}\n")

    parts.append(
        "war_manager={\n"
        "\tdatabase={\n"
        # Country 1 (JHG) fights an ongoing war; the same war is over for country 2.
        "0={\n"
        "\tdays_since_exhaustion=6\n"
        "\twar_participants={ {\n"
        "\t\t\tcountry=1\n"
        "\t\t\tviolator=4294967295\n"
        "\t\t} {\n"
        "\t\t\tcountry=7\n"
        "\t\t\tviolator=4294967295\n"
        "\t\t} }\n"
        "\tstart_date=1840.1.1\n"
        "\tpeace_date=1.1.1\n"
        "\tattacker_peace_deal={\n\tcountry=4294967295\n}\n"
        "}\n"
        # A concluded war must not be counted.
        "1={\n"
        "\twar_participants={ {\n"
        "\t\t\tcountry=1\n"
        "\t\t} }\n"
        "\tstart_date=1836.1.1\n"
        "\tpeace_date=1842.6.1\n"
        "}\n"
        "}\n"
        "}\n"
    )

    parts.append(
        "pacts={\n"
        "\tdatabase={\n"
        # SHU is the overlord of JHG and DMG (two subjects).
        "0={\n\ttargets={\n\t\tfirst=2\n\t\tsecond=1\n\t}\n\taction=tributary\n}\n"
        "1={\n\ttargets={\n\t\tfirst=2\n\t\tsecond=3\n\t}\n\taction=protectorate\n}\n"
        # TIB is a subject of KOR, so KOR has one subject while TIB has none.
        "2={\n\ttargets={\n\t\tfirst=8\n\t\tsecond=7\n\t}\n\taction=vassal\n}\n"
        # A non-subject pact must never be counted as a subject relationship.
        "3={\n\ttargets={\n\t\tfirst=2\n\t\tsecond=6\n\t}\n\taction=increase_relations\n}\n"
        "}\n"
        "}\n"
    )
    return "".join(parts)


class SaveExportFixture(unittest.TestCase):
    def setUp(self):
        self._temporary = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self._temporary.name)
        self.game_root = self.root / "game"
        (self.game_root / "common/subject_types").mkdir(parents=True)
        (self.game_root / "common/subject_types/00_subject_types.txt").write_text(
            SUBJECT_TYPES, encoding="utf-8"
        )
        self.save = self.root / "autosave.v3"
        self.save.write_text(build_save(), encoding="utf-8")

    def tearDown(self):
        self._temporary.cleanup()

    def write_save(self, text: str) -> pathlib.Path:
        self.save.write_text(text, encoding="utf-8")
        return self.save

    def export(self, **kwargs):
        return export(self.save, self.game_root, **kwargs)


class ExportHappyPathTest(SaveExportFixture):
    def test_reads_the_save_metadata(self):
        document = self.export()
        self.assertEqual(document["save"]["game_date"], "1846.1.1")
        self.assertEqual(document["save"]["game_version"], "1.13.11")
        self.assertEqual(document["save"]["mods"], "The Yongchang World")
        self.assertTrue(document["save"]["sha256"])
        self.assertEqual(document["checkpoint_year"], 1846)
        self.assertTrue(document["checkpoint_eligible"])

    def test_emits_one_row_per_core_country(self):
        rows = {row["country"]: row for row in self.export()["rows"]}
        self.assertEqual(set(rows), set(CORE_COUNTRIES))
        self.assertEqual(len(self.export()["rows"]), 10)

    def test_population_is_the_country_panel_figure(self):
        rows = {row["country"]: row for row in self.export()["rows"]}
        for identifier, tag in TAGS.items():
            self.assertEqual(rows[tag]["population"], sum(STRATA[identifier]), tag)
        self.assertEqual(self.export()["population_source"]["SHU"], "pop_statistics_strata")

    def test_rank_comes_from_the_ranking_table(self):
        rows = {row["country"]: row for row in self.export()["rows"]}
        self.assertEqual(rows["SHU"]["rank"], "unrecognized_major_power")
        self.assertEqual(rows["NMG"]["rank"], "unrecognized_power")

    def test_market_is_reported_as_the_owning_tag(self):
        rows = {row["country"]: row for row in self.export()["rows"]}
        self.assertEqual(rows["SHU"]["market"], "SHU")
        self.assertEqual(rows["KOR"]["market"], "SHU")

    def test_only_ongoing_wars_are_counted(self):
        rows = {row["country"]: row for row in self.export()["rows"]}
        self.assertEqual(rows["JHG"]["wars"], 1)
        self.assertEqual(rows["TIB"]["wars"], 1)
        self.assertEqual(rows["SHU"]["wars"], 0)

    def test_only_subject_pacts_are_counted_and_first_is_the_overlord(self):
        rows = {row["country"]: row for row in self.export()["rows"]}
        self.assertEqual(rows["SHU"]["subjects"], 2)
        self.assertEqual(rows["KOR"]["subjects"], 1)
        self.assertEqual(rows["TIB"]["subjects"], 0)
        self.assertEqual(rows["MGL"]["subjects"], 0)

    def test_error_count_comes_from_the_run_log(self):
        log = self.root / "error.log"
        log.write_text("[a] one\n\n[b] two\n", encoding="utf-8")
        document = self.export(error_log=log)
        self.assertEqual(document["error_count"], 2)
        self.assertEqual({row["error_count"] for row in document["rows"]}, {2})

    def test_missing_error_log_is_refused(self):
        with self.assertRaises(SaveExportError):
            self.export(error_log=self.root / "absent.log")


class ExportRefusalTest(SaveExportFixture):
    def test_a_save_outside_a_checkpoint_year_is_refused(self):
        self.write_save(build_save(date="1836.4.1"))
        with self.assertRaises(SaveExportError) as caught:
            self.export()
        self.assertIn("checkpoint year", str(caught.exception))

    def test_any_date_diagnoses_but_marks_the_export_ineligible(self):
        self.write_save(build_save(date="1836.4.1"))
        document = self.export(allow_any_date=True)
        self.assertEqual(document["checkpoint_year"], 1836)
        self.assertFalse(document["checkpoint_eligible"])

    def test_asserted_year_must_match_the_save(self):
        with self.assertRaises(SaveExportError) as caught:
            self.export(year=1866)
        self.assertIn("1866", str(caught.exception))

    def test_asserted_year_must_be_a_checkpoint_year(self):
        self.write_save(build_save(date="1837.1.1"))
        with self.assertRaises(SaveExportError):
            self.export(year=1837, allow_any_date=True)

    def test_a_missing_core_country_is_refused(self):
        self.write_save(build_save(omit_country="NMG"))
        with self.assertRaises(SaveExportError) as caught:
            self.export()
        self.assertIn("NMG", str(caught.exception))

    def test_a_country_without_a_rank_is_refused(self):
        text = build_save().replace(
            "\t\t\trank=unrecognized_power\n\t\t\ttarget=minor_power\n"
            "\t\t\tprestige=1\n\t\t\tscore=1\n\t\t\tcountry=10\n",
            "",
        )
        self.write_save(text)
        with self.assertRaises(SaveExportError) as caught:
            self.export()
        self.assertIn("rank", str(caught.exception))

    def test_a_missing_save_is_refused(self):
        with self.assertRaises(SaveExportError):
            export(self.root / "nope.v3", self.game_root)

    def test_a_game_root_without_subject_types_is_refused(self):
        empty = self.root / "empty-game"
        empty.mkdir()
        with self.assertRaises(SaveExportError) as caught:
            export(self.save, empty)
        self.assertIn("subject_types", str(caught.exception))


class PopulationCrossCheckTest(SaveExportFixture):
    # SHU's pops carry workforce + dependents for its strata total; nudging that
    # single value is how the two population methods are made to disagree.
    SHU_WORKFORCE = sum(STRATA[2]) - 5

    def test_a_pops_total_far_from_the_strata_total_is_reported(self):
        text = build_save().replace(
            f"\tworkforce={self.SHU_WORKFORCE}\n", "\tworkforce=9000000\n", 1
        )
        self.write_save(text)
        warnings = self.export()["warnings"]
        self.assertEqual(len(warnings), 1, warnings)
        self.assertIn("pops-by-state", warnings[0])

    def test_rounding_sized_differences_do_not_warn(self):
        text = build_save().replace(
            f"\tworkforce={self.SHU_WORKFORCE}\n", f"\tworkforce={self.SHU_WORKFORCE - 5000}\n", 1
        )
        self.write_save(text)
        self.assertEqual(self.export()["warnings"], [])
        self.assertEqual(self.export(cross_check_population=False)["warnings"], [])

    def test_missing_strata_falls_back_to_the_pops_sum_and_says_so(self):
        text = build_save().replace("\t\tpopulation_upper_strata=3\n", "", 1)
        self.write_save(text)
        document = self.export()
        rows = {row["country"]: row for row in document["rows"]}
        self.assertEqual(document["population_source"]["NMG"], "pops_by_state_workforce_and_dependents")
        self.assertEqual(rows["NMG"]["population"], sum(STRATA[10]) - 0)
        self.assertTrue(any("NMG" in warning for warning in document["warnings"]))


class OutputFormatTest(SaveExportFixture):
    def test_csv_columns_match_what_record_checkpoint_accepts(self):
        document = self.export()
        target = self.root / "1846.csv"
        write_csv(document, target)
        with target.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            self.assertEqual(tuple(reader.fieldnames), CSV_COLUMNS)
            self.assertEqual(len(list(reader)), 10)

    def test_record_checkpoint_loads_the_exported_rows(self):
        document = self.export()
        target = self.root / "1846.csv"
        write_csv(document, target)
        rows = load_rows(target, 1846)
        self.assertEqual(len(rows), 10)
        self.assertEqual({row["country"] for row in rows}, set(CORE_COUNTRIES))
        self.assertTrue(all(row["year"] == 1846 for row in rows))


class SubjectVocabularyTest(unittest.TestCase):
    def test_actions_are_derived_from_the_installed_game(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            directory_path = root / "common/subject_types"
            directory_path.mkdir(parents=True)
            (directory_path / "00_subject_types.txt").write_text(SUBJECT_TYPES, encoding="utf-8")
            self.assertEqual(load_subject_actions(root), {"tributary", "protectorate", "vassal"})

    def test_real_game_subject_types_match_the_save_action_names(self):
        game_root = pathlib.Path(r"E:/SteamLibrary/steamapps/common/Victoria 3/game")
        if not (game_root / "common/subject_types").is_dir():
            self.skipTest("installed game not available")
        actions = load_subject_actions(game_root)
        self.assertIn("tributary", actions)
        self.assertIn("protectorate", actions)
        self.assertIn("vassal", actions)
        self.assertNotIn("increase_relations", actions)


if __name__ == "__main__":
    unittest.main()
