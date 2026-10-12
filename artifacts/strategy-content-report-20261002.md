# Strategy and event content handoff

## Scope completed

- Added opening AI strategies, country selection flavor, and three-stage journal/event chains for 56 active registry starts not covered by existing campaigns. Country-specific geopolitical copy is bilingual. Logical Mongol tag `MNG` is excluded; runtime Khalkha uses `MGL`; Brazilian Minas Gerais keeps vanilla `MNG` untouched. Non-live `SIK` is excluded.
- Added bilingual safe fallback options to all 20 competing route-start events (`ywc_{shu,jhg,dmg,nqg,oir,mng,tib,kor,lan,nmg}.{4,5}`). Each fallback is `default_option` and `fallback`, and only applies its route's existing 90-day `_abandonment_cooldown`; the corresponding monthly pulse already checks that cooldown.
- Added valid vanilla event-image clips to all 491 country events, including generated campaign, frontier, hegemony, and southwest events. Generator changes are in `tools/build_{campaign,frontier_polity,hegemony,southwest}_content.py`; generated outputs were rebuilt.
- Added focused tests for tag coverage, MNG/MGL alias safety, event imagery, route fallback/localization contracts, and event/journal reachability.
- Added UTF-8 BOMs to all mod `.txt` and `.yml` files missing one (one file found in the cross-agent sweep: `common/history/military_formations/ywc_coastal_military_formations.txt`); frontier generator now writes every generated output with a BOM. Added a direct BOM-writer regression test.
- Corrected the four campaign full-settlement gates that referenced nonexistent answer stages 8/10/14/16/20/22/26/28. They now check the actual answering countries and valid stages 2, 4, or 5, restoring reachable full-settlement choices and removing the corresponding static “used but never set” warnings. Added a catalog contract test.
- Expanded the localization integrity test to recognize the new `.e` fallback option keys; English and Chinese labels were already present.

## Counts and verification

- Reachability: 491 events, 142 journals; no dangling references, unreferenced content, or unused helpers.
- Targeted tests: `python -m unittest tests.test_frontier_polity_content tests.test_content_reachability -v` — 13 passed.
- Static script validation: `python tools/ywc_check.py --mod-root yongchang_world --game-root 'E:\SteamLibrary\steamapps\common\Victoria 3\game'` — exit 0.
- Generator checks passed for campaign, frontier, hegemony, and southwest.
- The 46-test focused bundle passed, including reference integrity and metadata/BOM tests. `ywc_campaign_check.py --root .` passed with 180 events, 30 chapter journals, and 5 crisis journals.
- Scoped `git diff --check` reported no whitespace errors; Git printed only its usual LF-to-CRLF notices.

## Limitation

`python -m unittest discover -s tests` was started but interrupted after output showed a failure among the first tests; the suite did not finish, so the failing test was not identified here. The focused tests and static checks above passed. No independent in-game UI/runtime confirmation was performed by this subtask.
