# NMG negotiated market autonomy implementation plan

**Goal:** Allow a paying New Ming to ask its actual Mexican overlord for a concrete, revocable market right without rewriting existing remittance contracts.

**Architecture:** A repeatable bounded vanilla decision sends a captured request to a new recipient-side response. Acceptance creates a uniquely named pact whose maintenance reads the existing fixed-contract generation, payment ledger, actual direct subject and finance state; no script removes or rewrites unrelated pacts. Existing ledger and country queue remain authoritative.

**Spec:** `docs/superpowers/specs/2026-10-28-nmg-market-autonomy-design.md`.

**Boundaries:** Offline source and model only; no Victoria 3, Steam, launcher, UI, save, AI or performance acceptance. Do not merge or release. Preserve old `right = 1` semantics and existing debt.

1. Add a narrow failing source-driven test fixture for the decision, exact recipient, refusal, old/stale requests and captured contract/market identity; prove no unsigned right or payment mutation.
2. Add the guarded decision, request protocol, independent response event, locally named pact, subject-change/timeout invalidation and bilingual text. Use the documented `market_owner` and maintenance semantics; no assumption that `forced_duration` is an expiry timer.
3. Extend the offline interpreter only for typed direct-subject and pact/market operations needed by the actual source; include positive and negative maintenance, arrears, partner loss/recreation, external pact, and late-stage/closed-arc regressions.
4. Regenerate NMG outputs, independently review the source, freeze all inputs, run targeted and cross-country tests, installed-source validators and diff checks; compare frozen hashes.
5. Stage only task files, scan and commit, then push a scoped draft based on the NQG port concession branch. Record engine and full-v0.3 quota limits honestly.
