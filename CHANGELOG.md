# Changelog

## v0.1.0-rc1 (prepared)

- Added the ten-country Yongchang World content slice for Victoria 3 1.13.11 (Matcha).
- Added bounded AI guardrails and DLC compatibility gates for `ep1_content`, `mp1_content`, and `ep2_content`.
- Added hidden-launch mount checks, bilingual content, political identities, dynamic names, colors, and pure-color CoA placeholders.
- Added the `ywc_nmg_autonomy_negotiation` diplomatic pact action: New Ming can open autonomy negotiations with Mexico while a subject and carrying the New Ming–Mexico chain journal; acceptance resolves the chain. Bilingual localization included.
- Fixed the observation runner writing a UTF-8 BOM `content_load.json`, which the game rejects and silently falls back to "all DLC enabled, no mods". The runner now writes BOM-free JSON and records `mod_mount`, version-match evidence, observed DLC mounts, and ownership-backend state per hidden launch.
- Probes established that directly launched executables ignore `disabledDLC` when the ownership backend reports ownership, and that the backend flips between all-owned and none-owned across launches; single-DLC observation configs remain pending instead of being claimed as loaded.
- The 15-run / three-seed observation matrix is prepared but remains pending manual UI observation; no long-run statistics are claimed.

Known limits: the mod does not change base map geometry, some regional starts use Province subsets, and NMG remains a contested Mexican autonomous subject.
