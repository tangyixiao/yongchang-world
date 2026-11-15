"""JHG dockyard reserved source and exact old-arc preservation contracts."""
import hashlib
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
SLUG='v03_jhg_dockyard_capital'
OLD={
 'v03_jhg_court_assembly':'c0af2394cc02a8db4a0826ff436e3ee82eba0ff82cab2e16db7e4b109b65fcaa',
 'v03_jhg_convoy_capacity':'84c08f09b141a3e643f21e035fbb50fe9e0c1d6fa71b9807572a0b6bb8dd8798',
 'v03_jhg_tribute_autonomy':'f99e8ac07bad9278afcc2f10522f4c539882b3e62956a13364aab77919530f9f',
}

def source():
 return json.loads((ROOT/'data/content/v03/countries/jhg.json').read_text(encoding='utf-8-sig'))

def digest(value):
 return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()

class JhgDockyardInventory(unittest.TestCase):
 def test_reserved_eight_events_two_journals_and_existing_arcs(self):
  catalog=source(); arcs={a['slug']:a for a in catalog['arcs']}
  self.assertTrue(SLUG in arcs,'the dockyard story has not been implemented')
  arc=arcs[SLUG]
  self.assertEqual(len(arc['events']),8)
  self.assertEqual({e['id'] for e in arc['events']},{f'ywc_jhg.{i}' for i in range(1100,1108)})
  self.assertEqual(len(arc['journals']),2)
  self.assertEqual(len({j['id'] for j in arc['journals']}),2)
  for slug,expected in OLD.items():self.assertEqual(digest(arcs[slug]),expected,slug)

if __name__=='__main__':unittest.main()
