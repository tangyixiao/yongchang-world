# NQG Port Concessions Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans task by task. Steps use checkbox syntax.

**Goal:** Give an accepted, current NQG port agreement a concrete and honestly scoped state trade effect.
**Architecture:** Refresh one of two state modifiers on the exact captured state; remove them on suspension, expiry and the state owner-change callback. Existing captured partner and term guards remain authoritative.
**Tech Stack:** Victoria 3 Clausewitz, UTF-8 localized catalog, Python offline source interpreter and generator.
**Spec:** docs/superpowers/specs/2026-10-28-nqg-port-concessions-design.md

## Global Constraints

Offline source checks only; do not launch game, Steam or launcher. Preserve user work, contracts, queues and paid obligations. Do not describe a state-wide modifier as exclusive physical berths or a bilateral tariff.

## Review Focus

- Unsigned or refused offer must not receive either modifier.
- Ownership transfer removes the modifier immediately without retargeting.
- Partner/market loss suspends the modifier and only the same captured objects can restore it.
- Amendments replace the old modifier; an old scheduled endpoint cannot remove the new generation.
- A closed event arc and a subject change do not erase an otherwise active signed agreement.

### Task 1: Captured-state modifiers and source-model tests

**Files:** create tests/test_v03_nqg_port_concessions.py; modify tests/kor_partner_protocol_runtime.py only if a state-typed modifier primitive must be modelled; create yongchang_world/common/static_modifiers/ywc_v03_nqg_modifiers.txt and matching localization; modify ywc_v03_nqg_effects.txt and ywc_v03_nqg_accounts.txt.

**Interfaces:** consume ywc_nqg_port_treaty_lease_active, ywc_nqg_port_treaty_dest_state, captured berth/duty and generation. Produce ywc_nqg_port_treaty_refresh_concessions and two exclusive state modifiers.

- [ ] Write failing tests for the five review cases and both 0.5/0.6 amounts; run them to record RED.
- [ ] Add typed state-modifier test support without pretending to simulate the economy.
- [ ] Define the two modifiers and refresh/remove them at signing, monthly review, exact end, and state-owner change.
- [ ] Run the focused test file and existing NQG port response/regression tests; repair actual failures.

### Task 2: Truthful copy, independent review and frozen checks

**Files:** modify data/content/v03/countries/nqg.json and generated NQG event/localization files; update the prior NQG partner-response note; add a concise development note if needed.

- [ ] Describe the actual state-wide capacity and import tariff-cap effects, scope, and monthly delay in both languages; regenerate NQG output.
- [ ] Run independent source review and repair reproducible findings.
- [ ] Freeze exact tracked inputs, run NQG response/queue and cross-project tests, NQG/global generators, v0.3 and installed-source static validators and git diff --check; compare the frozen hashes.
- [ ] Stage only task files, inspect and scan staged content, commit, push a scoped draft PR stacked on the NMG joint-project branch; do not merge or release.
