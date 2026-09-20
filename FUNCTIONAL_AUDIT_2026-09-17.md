# Functional audit — September 17, 2026

Scope: frontend workflows and state, API/repository contracts, imports and bank synchronization, financial calculations, planning settings, assistant context, and demo behavior. Three Sol agents reviewed independent areas; the coordinating review checked their findings and ran additional reproductions. The findings and checks below describe the original audit snapshot. Subsequent review and fixes are recorded in [the repair review](C:/Users/tejas/Code/financial-planner/FUNCTIONAL_FIX_REVIEW_2026-09-19.md).

Priority: P1 means address first because financial activity or the active data mode can be misrepresented. P2 means a functional defect in a supported workflow. P3 means a narrower display/disclosure issue. Source-verified findings are distinguished from executed reproductions. No live bank connection or production database was modified.

## Checks performed

| Check | Result |
| --- | --- |
| Frontend unit suite | 61 tests passed in 23 files |
| Backend unit suite | 195 tests passed |
| Frontend lint and TypeScript | Passed |
| Backend Ruff and mypy | Passed; 113 source files type-checked |
| Next.js production build | Passed; all 16 pages generated |
| Five temporary component reproductions | Passed, confirming stale sensitivity, omitted projection defaults, duplicate session refresh, cross-account debt form state, and forced positive transfer amounts; temporary files removed |
| Focused Python/JavaScript reproductions | Confirmed import deduplication, sync overwrites, date handling, nullable settings, Monte Carlo exhaustion, zero-balance debt, assistant averages, and negative home-loan output |
| Local browser smoke check | Login, demo entry, Overview, Projections, Transactions, and Budget loaded; demo sensitivity unit defect observed |
| PostgreSQL integration / full authentication E2E | Not run: Docker daemon is unavailable; no isolated test database was started |

Passing tests do not cover the defects below. Frontend statement coverage was 27.26%; that is a coverage limitation, not itself a functional defect. Database/provider findings were checked against source and mocked repository reproductions, not a live Plaid/PostgreSQL run.

## Findings

### 1. P1 — CSV deduplication discards legitimate repeated purchases

**Trigger:** Import two purchases from the same merchant for the same amount on consecutive days, or two legitimate identical purchases on the same day.

**Observed:** A focused repository reproduction with two $5 Coffee Shop purchases on September 14 and 15 returned one created row and one skipped duplicate. Preview returned `[false, true]`. The three-day fuzzy match is applied within a single file, where repeated purchases are normal. Same-day repeats also share the unique import fingerprint. The preview's `include: true` cannot override this decision; final import reruns deduplication. Spending and subsequent projections become understated.

**Location:** [duplicate matching](C:/Users/tejas/Code/financial-planner/backend/app/persistence/repositories/transaction_repository.py:215), [fingerprint](C:/Users/tejas/Code/financial-planner/backend/app/persistence/repositories/transaction_repository.py:571), [import execution](C:/Users/tejas/Code/financial-planner/backend/app/api/v1/routes/transactions.py:264).

**Correction:** Distinguish transaction identity from a similarity warning, preserve repeated occurrences, and provide an explicit confirmed-import path for suspected duplicates.

### 2. P1 — Bank sync overwrites reviewed user classifications

**Trigger:** Manually classify a linked transaction as a transfer or edit its provider category, then receive a Plaid modified-transaction update.

**Observed:** Reproduced a reviewed transfer reverting to an expense and its edited category reverting to the provider category. The budget-category ID and reviewed timestamp remain, so the record still appears reviewed while its financial treatment changes. This can bring transfers back into spending totals.

**Location:** [unconditional provider overwrite](C:/Users/tejas/Code/financial-planner/backend/app/persistence/repositories/transaction_repository.py:376), [user classification](C:/Users/tejas/Code/financial-planner/backend/app/persistence/repositories/transaction_repository.py:466).

**Correction:** Persist provider values separately from user overrides and preserve the effective user classification during synchronization.

### 3. P1 — Demo transport and displayed account data can belong to different modes

**Trigger:** An authenticated user toggles demo mode while their dashboard data is fresh, or exits demo back to their signed-in account.

**Observed:** Source verification shows transport switches immediately, but DataProvider's effective authentication status stays `authenticated`. Its loading effect depends only on status and refresh tick, so it does not reload on the mode switch. Navigation only refreshes after the cache TTL. Real financial data can remain visible beneath the sample-data banner; the reverse can also happen. Actions can use stale IDs against the wrong data store.

**Location:** [load dependencies](C:/Users/tejas/Code/financial-planner/lib/data-provider.tsx:492), [mode toggle](C:/Users/tejas/Code/financial-planner/lib/auth-context.tsx:33).

**Correction:** Make mode/generation part of provider identity, cancel old requests, clear old state immediately, and reload before exposing actions. The signed-in transition was source-verified, not browser-tested against a real account.

### 4. P2 — Saved withdrawal defaults do not control new projections

**Trigger:** Save a 3% default withdrawal rate in Settings, then use the quick what-if or create a new rate-based scenario.

**Observed:** A component reproduction confirmed that the retirement request omits withdrawal rate. The API supplies 4%, independently of the saved profile. Scenario creation likewise falls back to its schema's 4% and 2.8% inflation instead of the user's saved defaults. At a $1 million retirement balance, 4% displays about $3,333/month versus $2,500/month at 3%.

**Location:** [quick request](C:/Users/tejas/Code/financial-planner/components/projection-assumptions.tsx:120), [scenario create defaults](C:/Users/tejas/Code/financial-planner/backend/app/schemas/scenario.py:28), [new scenario request](C:/Users/tejas/Code/financial-planner/components/new-scenario-dialog.tsx:127).

**Correction:** Seed new calculations/scenarios from the saved profile and send the effective assumptions explicitly. Preserve existing scenarios' intentional overrides.

### 5. P2 — Changing an income target leaves sensitivity results stale

**Trigger:** Edit only an existing scenario's desired monthly retirement income, including switching between income-target and rate-based mode.

**Observed:** A component rerender test changed the target from $4,000 to $8,000 and confirmed there was still only one sensitivity request and the old result remained. The dependency key includes age, contribution, and return, but omits desired income, withdrawal rate, and inflation. Backend sensitivity explicitly changes its calculation and final row depending on the target.

**Location:** [incomplete dependency key](C:/Users/tejas/Code/financial-planner/components/sensitivity-analysis.tsx:36), [target-dependent calculation](C:/Users/tejas/Code/financial-planner/backend/app/services/scenario_service.py:229).

**Correction:** Include all effective scenario assumptions and relevant allocation/profile inputs in invalidation.

### 6. P2 — Clearing planning goals reports success but retains their values

**Trigger:** Set a target savings rate or cash reserve target, then clear the input and save.

**Observed:** The frontend sends null, but the repository ignores null. Reproduction retained `0.2` and `10000` after explicitly clearing both. Refresh restores the old values. Date of birth has a related inability to clear: the frontend omits a blank value and the repository also ignores null.

**Location:** [null skipped](C:/Users/tejas/Code/financial-planner/backend/app/persistence/repositories/user_repository.py:95), [clear request](C:/Users/tejas/Code/financial-planner/components/settings-forms.tsx:152).

**Correction:** Distinguish an omitted field from an explicitly cleared nullable field.

### 7. P2 — Locally entered transactions become uneditable on linked accounts

**Trigger:** Manually enter or CSV-import a transaction into a linked bank account, then correct its amount, date, or merchant.

**Observed:** Creation/import is accepted, but updates reject these fields based solely on the account having an institution. This applies even when the transaction has no provider ID and was created locally. Source-verified API inconsistency.

**Location:** [manual creation](C:/Users/tejas/Code/financial-planner/backend/app/api/v1/routes/transactions.py:132), [linked-account restriction](C:/Users/tejas/Code/financial-planner/backend/app/persistence/repositories/transaction_repository.py:419).

**Correction:** Determine edit ownership per transaction, not solely per account, or disallow the unsupported creation path with an explanation.

### 8. P2 — Dashboard, outlook, and assistant use different history windows

**Trigger:** Connect an account with only a few months of history or a first imported month that starts midmonth.

**Observed:** The assistant divides by 12 regardless of coverage and includes the current month. The dashboard excludes the current month but includes the first partial month. Backend outlook/health use the shared completed-month helper, excluding both partial months. A mocked assistant context with three months of $4,000 income and $2,000 expenses reported $1,000 income and $500 expenses per month. Users receive different surplus estimates for the same imported activity.

**Location:** [assistant fixed divisor](C:/Users/tejas/Code/financial-planner/backend/app/ai/context.py:33), [dashboard averaging](C:/Users/tejas/Code/financial-planner/lib/data-provider.tsx:266), [backend coverage policy](C:/Users/tejas/Code/financial-planner/backend/app/services/activity_history.py:19).

**Correction:** Share coverage-aware window semantics and communicate when history is insufficient instead of treating missing months as zero activity.

### 9. P2 — Brokerage cash counts as liquidity on one screen but not another

**Trigger:** Hold accessible cash or a cash-equivalent position in a taxable brokerage account, with little or no depository cash.

**Observed:** Dashboard and Insights include cash holdings; the financial-health liquidity score and assistant snapshot use only positive depository balances. A $10,000 brokerage cash holding can coexist with a zero liquidity score and a positive cash-buffer insight.

**Location:** [snapshot definition](C:/Users/tejas/Code/financial-planner/backend/app/domain/entities.py:183), [health score](C:/Users/tejas/Code/financial-planner/backend/app/services/financial_health_service.py:65), [dashboard definition](C:/Users/tejas/Code/financial-planner/lib/data-provider.tsx:283).

**Correction:** Use a shared liquidity definition, explicitly separating accessible brokerage cash from restricted retirement cash.

### 10. P2 — Birthday handling advances age one day early in US time zones

**Trigger:** Use the app on the day before a birthday west of UTC.

**Observed:** Executing the actual helper in America/New_York with DOB `1990-09-18` and local date September 17, 2026 returned age 36 instead of 35. A date-only string is parsed as UTC then compared using local month/day. Backend age arithmetic does not have this error. This shifts retirement horizons and calendar labels.

**Location:** [age parsing](C:/Users/tejas/Code/financial-planner/lib/dashboard-data-helpers.ts:8).

**Correction:** Treat birth dates as calendar dates, without timezone conversion.

### 11. P2 — Skipping date of birth silently models the user as age 35

**Trigger:** Select “Skip for now” during onboarding without saving DOB.

**Observed:** Source verification shows `ageFromBirthDate(null)` returns 35, which is then used as the current age for projections and scenario previews. The UI does not identify this as an assumption. The assistant, in contrast, receives an unavailable age.

**Location:** [invented default](C:/Users/tejas/Code/financial-planner/lib/dashboard-data-helpers.ts:7), [use in planning](C:/Users/tejas/Code/financial-planner/lib/data-provider.tsx:221).

**Correction:** Require an explicit age for age-dependent calculations or prominently expose a user-adjustable assumed age.

### 12. P2 — Already-paid debt is reported as not paid off

**Trigger:** Include a still-open loan/credit account with a zero balance and saved debt terms in payoff planning.

**Observed:** Reproduced a zero-month plan with an empty payoff order. The API compares payoff-order length with selected account count and returns `paid_off=false`, with a warning that repayment did not finish within 600 months.

**Location:** [completion check](C:/Users/tejas/Code/financial-planner/backend/app/api/v1/routes/simulations.py:213).

**Correction:** Treat zero starting balances as already paid, or determine success from remaining debt rather than the number of payoff events.

### 13. P2 — Monte Carlo rejects exact final-payment funding

**Trigger:** A trial can pay every required withdrawal but finishes at exactly zero, or requires no withdrawals from a zero balance.

**Observed:** Reproduced $100 starting balance, one retirement year, $100 withdrawal, zero return/volatility: Monte Carlo reports 0% success. Deterministic feasibility explicitly accepts exact final exhaustion. The Monte Carlo code flags every post-withdrawal balance `<= 0` as failure.

**Location:** [failure condition](C:/Users/tejas/Code/financial-planner/backend/app/simulation/monte_carlo.py:127), [deterministic semantics](C:/Users/tejas/Code/financial-planner/backend/app/services/retirement_projection_service.py:111).

**Correction:** Track whether each required withdrawal was funded; reaching zero after the last funded payment is different from failing a payment.

### 14. P2 — Saved simulation metadata does not match the inputs actually used

**Trigger:** Save a scenario run with nonzero inflation.

**Observed:** The engine receives volatility divided by `1 + inflation`, while the stored assumptions report the unadjusted volatility. Defaults produce about 0.1031128 in execution versus 0.106 in the snapshot. Metadata also says nominal returns were deflated although the expected return was supplied as real. Source-verified mismatch; no double inflation subtraction was found in the return calculation itself.

**Location:** [actual inputs](C:/Users/tejas/Code/financial-planner/backend/app/services/scenario_service.py:117), [stored metadata](C:/Users/tejas/Code/financial-planner/backend/app/api/v1/routes/scenarios.py:210).

**Correction:** Record the exact executed inputs and correct their stated dollar/return basis so saved runs are reproducible.

### 15. P2 — Income-target scenarios have misleading income/success explanations

**Trigger:** Set a fixed monthly income target rather than using a withdrawal-rate plan.

**Observed:** Decumulation and Monte Carlo use the fixed target, but success tooltips state the withdrawal is a percentage of the scenario's balance. The comparison table's monthly income is the separate withdrawal-rate amount. For a $1 million balance, 4% rate, and $4,000 target, the table shows $3,333.33 while the trajectory models $4,000. The target badge helps but does not correct the tooltip or clearly distinguish these metrics.

**Location:** [comparison explanation](C:/Users/tejas/Code/financial-planner/components/scenario-compare.tsx:14), [actual target selection](C:/Users/tejas/Code/financial-planner/backend/app/services/retirement_projection_service.py:82), [card tooltip](C:/Users/tejas/Code/financial-planner/app/(app)/projections/page.tsx:197).

**Correction:** Label withdrawal-rate capacity and modeled spending separately; make success explanations conditional on plan mode.

### 16. P2 — Transaction pagination is not repaired after a result-changing edit/delete

**Trigger:** View page two with 51 total matching transactions, then delete the last matching row or edit it out of the current filter.

**Observed:** Source verification shows the reload retains offset 50 even though total becomes 50. The page is empty and its range becomes “Showing 51–50 of 50.” Filter changes reset pagination, but mutation reloads do not clamp it.

**Location:** [range calculation](C:/Users/tejas/Code/financial-planner/app/(app)/transactions/page.tsx:244), [mutation reload](C:/Users/tejas/Code/financial-planner/app/(app)/transactions/page.tsx:264).

**Correction:** Move to the last valid page and refetch when the current page no longer exists.

### 17. P2 — Scenario save failure can conceal a successful save

**Trigger:** A scenario PATCH succeeds, then the immediately following simulation run fails.

**Observed:** Both calls share one catch. The UI reports it could not save, keeps the dialog open, and skips refresh even though the new assumptions are persisted. Source-verified partial-commit path.

**Location:** [save/run sequence](C:/Users/tejas/Code/financial-planner/components/new-scenario-dialog.tsx:105).

**Correction:** Acknowledge and refresh the successful save separately from an unsuccessful projection run.

### 18. P2 — Category/rule failure can conceal a successful transaction change

**Trigger:** Assign a category/classification and choose to create a merchant rule; the assignment succeeds but rule creation fails.

**Observed:** Transactions reports “Couldn't update that category” even though the row changed. The dialog closes, leaving the user uncertain what was saved. Budget already distinguishes partial success for the equivalent workflow.

**Location:** [multi-step assignment](C:/Users/tejas/Code/financial-planner/app/(app)/transactions/page.tsx:210).

**Correction:** Report the saved transaction and failed rule separately, or make the operation atomic.

### 19. P2 — Linked holdings are protected on create but not edit/delete

**Trigger:** Call PATCH/DELETE for a holding owned by the user in an active linked institution account.

**Observed:** Creation explicitly rejects provider-managed accounts. Update/delete check ownership and archive status but not provider management, so they allow inconsistent local mutations that the next holdings sync replaces. This is an API-level source finding; no live holding was modified.

**Location:** [create-only guard](C:/Users/tejas/Code/financial-planner/backend/app/api/v1/routes/financial_inputs.py:99), [unguarded updates](C:/Users/tejas/Code/financial-planner/backend/app/persistence/repositories/holding_repository.py:48).

**Correction:** Enforce a consistent ownership policy for all holding mutations or implement explicit persistent overrides.

### 20. P3 — Demo sensitivity renders a dollar balance as a percentage

**Trigger:** Enter demo mode and open Projections.

**Observed in browser:** The sensitivity row displayed `+2415292.89%`. The demo API returns the retirement balance with kind `illustration`; the renderer formats everything other than `success_pp` as a percentage. The panel also says “computed live, not illustrative” while the row calls itself illustrative.

**Location:** [demo response](C:/Users/tejas/Code/financial-planner/lib/demo-api.ts:170), [unit handling](C:/Users/tejas/Code/financial-planner/components/sensitivity-analysis.tsx:135).

**Correction:** Return an actual sensitivity delta, or explicitly render an illustrative dollar value with matching disclosure.

## Continuation findings

The second pass focused on account editing, automatic loan reductions, synchronization refresh boundaries, transaction entry, and session restoration. Findings that merely restated existing defects or contradicted an explicit product disclosure were excluded.

### 21. P1 — Correcting or deleting an automated loan payment leaves the wrong balance

**Trigger:** A merchant-linked payment reduces a manual loan balance; subsequently correct the payment amount, change its merchant/status, or delete the transaction.

**Observed:** A focused reproduction using the real merchant application/reduction methods returned:

```text
Original $100 payment: applied=1, loan balance=-900
Correct payment to $10: applied=0, loan balance=-900
Soft-delete payment:   applied=0, loan balance=-900
```

The corresponding balances should be -990 after correction and -1000 after removing the payment, assuming no other changes. Adjustments store the original amount and transaction ID, but mutation paths never reconcile them. Subsequent automation skips the already-applied ID permanently.

**Location:** [idempotency/reduction](C:/Users/tejas/Code/financial-planner/backend/app/services/loan_balance_automation_service.py:126), [transaction mutation routes](C:/Users/tejas/Code/financial-planner/backend/app/api/v1/routes/transactions.py:148).

**Correction:** Reconcile persisted adjustments when their source transactions change or disappear, including provider corrections/removals, while preserving an auditable balance history.

### 22. P1 — Overlapping payment rules reduce the same loan twice

**Trigger:** Create two merchant rules for the same manual loan that match the same outgoing transaction, such as `acme` and `acme loan`, or accidentally duplicate the selected merchant rule.

**Observed:** A reproduction with a -$1,000 loan and one $100 payment produced a -$800 loan balance and two adjustment records. Idempotency is per rule, so each rule independently treats the same payment as new. Creation has no overlap/duplicate guard. This contradicts the UI's once-per-transaction description.

**Location:** [rule iteration](C:/Users/tejas/Code/financial-planner/backend/app/services/loan_balance_automation_service.py:77), [per-rule event lookup](C:/Users/tejas/Code/financial-planner/backend/app/services/loan_balance_automation_service.py:134).

**Correction:** Deduplicate merchant payment application per target loan and source transaction, and reject redundant rules or define explicit splitting semantics.

### 23. P1 — Debt details from one account can be saved into another

**Trigger:** Open loan A's details, close the dialog, then open loan B before its request completes and press Save; alternatively, let a slow response for A arrive after B.

**Observed:** A component reproduction loaded A with a $1,000 principal/$100 minimum payment, switched through the closed state to B, and pressed Save before B loaded. The actual component called `saveLiability("B", ...)` with A's values. The parent keeps this component mounted when `account=null`; the effect neither clears old values nor guards late responses. Save remains enabled during loading.

**Location:** [persistent dialog state and unguarded requests](C:/Users/tejas/Code/financial-planner/components/financial-details-dialog.tsx:43), [save using current account ID](C:/Users/tejas/Code/financial-planner/components/financial-details-dialog.tsx:67).

**Correction:** Reset state on account changes, guard request results by account/generation, and disable mutations until the selected account has successfully loaded. Apply the same handling to holdings/rules.

### 24. P1 — Concurrent refreshes can invalidate otherwise valid sessions

**Trigger:** Initial authentication effects run twice under React StrictMode, or two browser tabs refresh the shared cookie before either response rotates it.

**Observed:** A StrictMode component reproduction issued two bootstrap refresh calls. With the first succeeding and the second rejected as already consumed, the provider ended unauthenticated. Bootstrap refresh is not covered by the transport's in-flight refresh promise. Backend source shows the second consume of a revoked token calls `revoke_all` for the user, including the newly rotated session and other sessions. Thus an ordinary concurrency race is treated as token replay.

**Location:** [bootstrap request](C:/Users/tejas/Code/financial-planner/lib/auth-context.tsx:76), [replay-wide revocation](C:/Users/tejas/Code/financial-planner/backend/app/persistence/repositories/refresh_session_repository.py:39).

**Correction:** Deduplicate bootstrap refreshes, coordinate refresh across tabs or safely handle concurrent rotation, and retain intentional replay protection. The frontend duplication/result was reproduced; PostgreSQL cross-tab concurrency still needs integration coverage.

### 25. P2 — Accepted long passwords are silently truncated by hashing

**Trigger:** Register or reset to a password longer than bcrypt's 72-byte input limit; the API accepts up to 128 characters.

**Observed:** Executed the real schema/hash/verification functions using two distinct synthetic 73-character passwords with the same first 72 characters. A hash of the first verified successfully with the second. Multibyte characters reach the byte limit earlier than the character limit. The application accepts a secret it does not fully check.

**Location:** [accepted length](C:/Users/tejas/Code/financial-planner/backend/app/schemas/auth.py:7), [bcrypt context](C:/Users/tejas/Code/financial-planner/backend/app/core/security.py:12).

**Correction:** Use a password-hashing scheme that supports the accepted input length with an explicit migration path, or reject inputs exceeding the supported byte limit consistently at registration/reset.

### 26. P2 — Rejected refresh responses do not actually clear the stale cookie

**Trigger:** A refresh token is found invalid/revoked, so the refresh handler calls its cookie-clearing helper then raises HTTPException.

**Observed:** An isolated FastAPI TestClient reproduction returned HTTP 401 with **no Set-Cookie header**. Raising the exception discards the injected Response on which deletion was set. The browser retains the invalid cookie and retries it on later restoration; combined with replay-wide revocation this can repeatedly invalidate other sessions.

**Location:** [discarded response mutation](C:/Users/tejas/Code/financial-planner/backend/app/api/v1/routes/auth.py:144).

**Correction:** Return the actual error response carrying cookie deletion or attach it through the exception/handler response path.

### 27. P2 — Manual entry cannot represent outgoing transfers/card payments correctly

**Trigger:** Add a $500 transfer out of checking, an outgoing credit-card payment, or an outgoing investment contribution.

**Observed:** A component reproduction confirmed Transfer is submitted as positive `500`. Manual entry permits only positive input and forces every type except Expense to positive. There is no direction control. Ledger direction/color are wrong, and an outgoing transfer assigned a budget category can become a reimbursement in budget calculations. Expense refunds likewise cannot be entered through this form as positive expense amounts.

**Location:** [forced sign](C:/Users/tejas/Code/financial-planner/components/transaction-entry-dialog.tsx:60).

**Correction:** Collect explicit money direction or accept a validated signed amount independently from transaction classification, including refunds.

### 28. P2 — Investment/allocation displays stay stale after successful changes

**Trigger:** Sync accounts from the top bar while staying on Investments; or add/delete a manual holding and navigate to Overview before the provider's two-minute freshness interval expires.

**Observed:** Source verification shows Investments fetches its own dashboard only on mount. Top-bar sync refreshes DataProvider, not that local dashboard. Manual holding changes update only the dialog's local list and do not refresh the global allocation provider. A successful action can leave old balances, holdings, allocation, or gains visible until remount/refresh.

**Location:** [mount-only dashboard load](C:/Users/tejas/Code/financial-planner/app/(app)/investments/page.tsx:29), [local-only holding update](C:/Users/tejas/Code/financial-planner/components/financial-details-dialog.tsx:78), [top-bar refresh](C:/Users/tejas/Code/financial-planner/components/topbar.tsx:36).

**Correction:** Centralize refresh/invalidation or expose a shared generation that all dependent page queries observe; notify it after holding mutations.

### 29. P2 — Optional account details cannot be cleared in the editor

**Trigger:** Edit a manual account, delete its existing APY or account mask, and save.

**Observed:** The editor converts blanks to undefined. JSON omits them, so PATCH receives no instruction to clear the saved values; reopening shows the old values. In particular, a stale APY can continue to influence recommendations and cash growth assumptions.

**Location:** [omitted blank fields](C:/Users/tejas/Code/financial-planner/components/manual-account-dialog.tsx:69).

**Correction:** Send explicit null for cleared optional fields and ensure the repository distinguishes null from omission.

## Additional bounded issues and validation gaps

- **Home-affordability output can report negative borrowing.** Executed the tool with $2,000 gross monthly income, $650 monthly debt, and $100,000 available down payment: maximum home price was $56,000 and maximum loan amount was **-$44,000**. The price can reasonably be limited by carrying costs, but borrowing should be zero and unused cash separate. [Output subtraction](C:/Users/tejas/Code/financial-planner/backend/app/ai/tools/recommendation_tools.py:57).
- **Negative net contributions become negative assets.** The API permits negative contributions; with no accounts and -$1,000 annual contribution, the service returns assets -$1,000 and liabilities zero. The synthetic contribution bucket also compounds the deficit as an investment. Define withdrawals/shortfalls explicitly instead. [Contribution bucket](C:/Users/tejas/Code/financial-planner/backend/app/services/net_worth_projection_service.py:94).
- **The Monte Carlo integration contract is stale.** The integration test requires `normal-iid-v2`, but the engine emits `normal-iid-monthly-contributions-v3`. This is a source-confirmed incompatible assertion; the integration suite was not executed. [Assertion](C:/Users/tejas/Code/financial-planner/backend/tests/integration/test_monte_carlo_contract.py:18), [engine version](C:/Users/tejas/Code/financial-planner/backend/app/simulation/monte_carlo.py:18).
- **Contribution help text contradicts the input period.** The scenario dialog calls the field monthly but says its amount is added “each year”; calculation correctly multiplies by 12. Correct the copy to prevent annual amounts being entered into a monthly field. [Help text](C:/Users/tejas/Code/financial-planner/components/new-scenario-dialog.tsx:212).
- **Social Security is not implemented in projections.** Settings discloses this as future functionality, so it is not counted as a hidden calculation bug. Onboarding presents an enabled “Include Social Security” option without the same caveat. Align onboarding disclosure with Settings. [Settings caveat](C:/Users/tejas/Code/financial-planner/components/settings-forms.tsx:400).
- **Historical budgets deliberately use current limits.** Browser inspection found a disclosure stating this. The global-limit design is therefore not counted as a confirmed defect, despite the potential for confusion when editing a past month.

## Suggested repair order

1. Preserve imported transaction multiplicity and user classifications during sync.
2. Make loan adjustments correction-safe and prevent overlapping rules from double-applying payments.
3. Isolate demo/live and cross-account form state; repair session refresh concurrency and cookie clearing.
4. Make settings and scenario assumptions propagate consistently; fix sensitivity invalidation, nullable clears, and refresh boundaries.
5. Unify transaction direction, history, liquidity, age, and retirement-success semantics across consumers.
6. Repair password-length handling, partial-commit feedback, pagination, API ownership guards, and demo/display issues.
7. Run PostgreSQL integration and real authentication E2E in an isolated environment, including the corrected model-version contract, before treating the scan as full runtime coverage.

At the end of the original audit, only this report was retained; temporary reproduction tests and the temporary local preview server were removed/stopped. Application fixes were subsequently requested and are tracked in the linked repair review.
