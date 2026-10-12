"""Regression for the engine's eager evaluation of missing route variables."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class JournalOptionalProgressTest(unittest.TestCase):
    def test_progress_comparisons_are_conditionally_evaluated(self):
        seen = 0
        for path in (ROOT / 'yongchang_world/common/journal_entries').glob('ywc_*.txt'):
            text = path.read_text('utf-8-sig')
            for match in re.finditer(r'var:(ywc_(?:route|je|jinghai)[A-Za-z0-9_]*_progress)\s*>=\s*100', text):
                seen += 1
                prefix = text[max(0, match.start() - 250):match.start()]
                self.assertRegex(prefix, rf'trigger_if\s*=\s*\{{\s*limit\s*=\s*\{{\s*has_variable\s*=\s*{match.group(1)}\s*\}}\s*$', str(path))
        self.assertGreaterEqual(seen, 22)


if __name__ == '__main__':
    unittest.main()
