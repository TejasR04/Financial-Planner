# Functional review and repairs — September 19, 2026

Three Sol agents reviewed the original findings for intent and implemented repairs in frontend workflows, transaction persistence, and financial calculations. The coordinating review handled authentication, reviewed the combined changes, and checked edge cases and browser behavior. This document supplements the historical [functional audit](C:/Users/tejas/Code/financial-planner/FUNCTIONAL_AUDIT_2026-09-17.md).

The confirmed defects have been repaired. No live bank connection or production database has been modified.

## Cash-flow change requested after the review

Actual spending now nets transactions assigned to active budget categories: expenses, refunds, and incoming/outgoing categorized transfers. This includes pending activity and excludes ignored transactions, card payments, and unassigned spending. Income includes positive classified income outside budget categories, such as paychecks and interest. Categorized reimbursements reduce spending instead of increasing income.

Clicking a chart bar opens the matching month's transactions. Spending is grouped by budget category with net subtotals and signed transaction amounts. A month selector and View expenses/View income buttons also expose zero-net months whose bars have no height. Dashboard averages, assistant context, and the cash-flow outlook share the same budget basis and authoritative completed-history window. Other financial-health calculations retain their existing, separately defined expense basis.

## Decisions by original finding

| # | Review decision and resulting behavior |
| --- | --- |
| 1 | Defect. CSV imports preserve repeated purchases and use stable row identities for replay. Similar existing activity is a warning with an explicit inclusion control. Exact imported identities remain protected against replay. |
| 2 | Defect. Provider classifications and user overrides are stored separately so bank updates preserve user choices. Existing reviewed linked transactions receive conservative override backfills. |
| 3 | Defect. Changing demo/live mode reloads and isolates the displayed data. Ordinary refreshes preserve the mounted interface. |
| 4 | Defect. Saved return, inflation, and withdrawal assumptions seed new scenarios and quick projections; explicit scenario overrides remain authoritative. |
| 5 | Defect. Sensitivity results are invalidated when the income target, inflation, or withdrawal assumptions change. |
| 6 | Defect. Explicit null clears optional birth date and planning goals. Omitted fields are preserved; required fields reject null. |
| 7 | Defect. Manual and CSV transactions remain editable on linked accounts. Provider-owned transactions retain their editing restrictions. |
| 8 | Defect. Dashboard and assistant averages use completed available months rather than fixed twelve-month or partial-month divisors. Missing completed history is reported as unavailable. |
| 9 | Defect. Accessible cash consistently includes positive depository balances and cash holdings in taxable brokerage accounts, excluding retirement cash. |
| 10 | Defect. Birth dates are interpreted as calendar dates rather than UTC timestamps. |
| 11 | Defect. Missing birth dates no longer silently imply age 35; planning asks for the missing information. |
| 12 | Defect. Zero-balance debts are already paid off. |
| 13 | Defect. A retirement simulation that exactly funds its final withdrawal succeeds. It fails when a required withdrawal cannot be funded. |
| 14 | Defect. Stored simulation metadata reports the volatility actually used and describes the real-dollar calculation accurately. |
| 15 | Defect. Scenario comparisons distinguish modeled spending from withdrawal-rate capacity; success descriptions follow the scenario's actual spending mode. |
| 16 | Defect. Transaction pagination adjusts when edits or removals shrink the filtered result set. |
| 17 | Defect. A successful scenario save followed by a failed run is reported as a saved scenario with a calculation failure. |
| 18 | Defect. A successful category change followed by a failed merchant-rule save is reported as a partial success. |
| 19 | Defect. Linked holdings reject manual updates and deletions as well as creation. |
| 20 | Defect. Demo sensitivity values use the declared dollar unit and are clearly described as illustrative. |
| 21 | Defect. Loan adjustment history supports corrections and source removals, with capped reductions accounted for. |
| 22 | Defect. A source payment cannot reduce the same loan twice through overlapping rules. |
| 23 | Defect. Account detail forms reset and guard loading/saving against account changes and stale responses. |
| 24 | Defect. Bootstrap and request recovery share session refresh, with cross-tab coordination where Web Locks are supported. Session changes invalidate stale requests. Replay protection remains enabled. |
| 25 | Defect. New passwords use bcrypt-SHA256 to check the full accepted input. Successful legacy bcrypt logins upgrade the stored hash. |
| 26 | Defect. Invalid refresh responses carry the cookie deletion, including the configured path, Secure, HttpOnly, and SameSite attributes. |
| 27 | Defect. Manual transactions have an explicit money direction independent of classification, supporting outgoing transfers and incoming refunds. |
| 28 | Defect. Investments observe shared refreshes; manual holding changes refresh dependent displays. |
| 29 | Frontend defect. Cleared optional account fields are submitted as null. The backend already distinguishes null from omission. |

## Deliberate behavior and bounded corrections

- Historical budgets deliberately use current limits and disclose this. That behavior is retained.
- Social Security remains unimplemented in projections. The existing Settings caveat is retained and onboarding now makes the limitation explicit.
- Pending activity remains included in the activity totals that explicitly disclose it.
- Loan merchant rules continue to start with transactions posted after the creation date, as disclosed. Deleting a rule stops future automation while retaining valid historical adjustments and their provenance.
- Merchant-wide classification rules remain merchant-wide; no unrequested per-purchase classification model was introduced.
- Home-affordability output now floors borrowing at zero and identifies unused down-payment cash.
- Negative net contributions are rejected because the current model has no defined withdrawal/shortfall treatment; it no longer fabricates negative investment assets.
- Monthly contribution help text now says each month. The Monte Carlo integration assertion matches the current monthly-contribution model version.

## Migration and compatibility

The new migration `c7d8e9f0a1b2` adds provider/user classification provenance, expands CSV import identities, and retains reversible loan adjustment history. It also repairs historical duplicate loan reductions from overlapping rules by restoring the duplicated amount to the loan balance. It must be applied before running the changed backend against an existing database. Downgrading preserves transaction rows but clears occurrence fingerprints that the old schema cannot represent; rollback therefore loses those replay identities.

Legacy reviewed classifications are preserved conservatively because the old schema did not identify which values the user changed. Legacy bcrypt hashes upgrade on successful login; their previously discarded password suffix cannot be reconstructed from the old hash.

## Validation

| Check | Result |
| --- | --- |
| Backend unit tests | 237 passed |
| Frontend unit tests | 77 passed across 26 files; final partial-history change also passed its 5 focused tests |
| Frontend ESLint and TypeScript | Passed |
| Backend Ruff and mypy | Passed; 115 source files type-checked |
| Migration head and offline upgrade/downgrade rendering | Passed; head `c7d8e9f0a1b2` |
| Browser workflow checks | Demo entry/exit, outgoing transfer direction, scenario metrics, monthly contribution copy, sensitivity currency/copy, and chart-bar transaction breakdowns verified |
| Production build | Passed; all 16 pages generated |
| PostgreSQL integration / authentication E2E | Not run: local Docker Linux engine unavailable |

Browser chart verification showed September demo spending of $3,210 grouped into six categories and income of $7,200 containing only the sample employer payment. Regression tests cover categorized Zelle offsets, zero-net categories, excluded activity, positive non-budget income, stale requests, and retry behavior.

Frontend statement coverage is 30.42%; passing checks do not imply exhaustive runtime coverage. Offline migration rendering and mocked repository tests do not substitute for a live database run. Browsers without Web Locks have same-tab refresh deduplication but lack cross-tab refresh serialization. Backend token-replay protection remains enabled. Temporary preview servers and test browser tabs were stopped/closed.
