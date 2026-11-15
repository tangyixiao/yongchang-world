# v0.3 quota accounting plan

**Problem:** The release quota checker currently counts every visible event. Recently added response and retry interfaces support existing stories but must not silently increase the count of independently authored narrative events. Hidden endpoints are already excluded.

**Approach:** Add a reviewed, explicit data file listing known operational response/menu events and reasons. The complete quota check excludes those IDs; it validates the list against the live catalogs and fails closed on a missing, malformed, duplicate or unknown entry. Unlisted visible events remain an upper bound, not proof of narrative quality or reachability. This is conservative accounting, not a release acceptance or an assertion that foreign decisions lack gameplay value.

1. Write failing tests for excluded visible IDs, ordinary visible events, hidden events, cross-owner quotas, missing/invalid/duplicate/unknown records and the known current protocol list.
2. Implement bounded metadata loading and pass the exclusions to the complete gate without changing runtime content or generated outputs.
3. Record the reason for each exclusion and the remaining manual quality-review boundary. Run catalog, quota, generator and cross-country regressions on a frozen snapshot and request independent review.
4. Commit only the scoped files and create a stacked draft. Do not claim the full version or engine acceptance is complete.
