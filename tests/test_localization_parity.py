import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).parents[1]
LOC_ROOT = ROOT / "yongchang_world/localization"
KEY_PATTERN = re.compile(r"^\s*([A-Za-z][A-Za-z0-9_.]*):\d+", re.MULTILINE)
LANGUAGES = ("english", "simp_chinese")


def base_name(path: pathlib.Path) -> str:
    """Strip the language suffix: ywc_core_l_english.yml -> ywc_core."""
    match = re.fullmatch(r"(.+)_l_(?:english|simp_chinese)\.yml", path.name)
    return match.group(1) if match else path.stem


def language_files(language: str) -> dict:
    return {base_name(p): p for p in (LOC_ROOT / language).glob("*.yml")}


def key_set(path: pathlib.Path) -> set:
    return set(KEY_PATTERN.findall(path.read_text("utf-8-sig")))


class LocalizationParityTest(unittest.TestCase):
    def test_every_english_file_has_a_chinese_counterpart(self):
        en_files = language_files("english")
        zh_files = language_files("simp_chinese")
        for name in sorted(en_files):
            self.assertIn(name, zh_files, f"missing simp_chinese counterpart for {name}_l_*")

    def test_key_sets_match_between_languages(self):
        en_files = language_files("english")
        zh_files = language_files("simp_chinese")
        for name, en_path in sorted(en_files.items()):
            self.assertIn(name, zh_files, f"missing simp_chinese counterpart for {name}_l_*")
            en = key_set(en_path)
            zh = key_set(zh_files[name])
            self.assertEqual(
                en - zh,
                set(),
                f"{name}: keys missing in simp_chinese: {sorted(en - zh)[:10]}",
            )
            self.assertEqual(
                zh - en,
                set(),
                f"{name}: keys missing in english: {sorted(zh - en)[:10]}",
            )

    def test_no_placeholder_style_journal_names(self):
        # Display-name keys must not remain lower-case echoes of the key name.
        placeholder = re.compile(r"^\s*(ywc_[A-Za-z0-9_]+):\d+\s+\"([a-z0-9 _\-]+)\"\s*$")
        for language in LANGUAGES:
            for path in sorted((LOC_ROOT / language).glob("*.yml")):
                for line in path.read_text("utf-8-sig").splitlines():
                    match = placeholder.match(line)
                    if match:
                        self.fail(
                            f"{path}:{match.group(1)} is still a placeholder "
                            f"(\"{match.group(2)}\")"
                        )


if __name__ == "__main__":
    unittest.main()
