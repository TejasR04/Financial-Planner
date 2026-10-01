# Meridian manual demo audit

> **Scope correction (September 29):** This document records what the deployed demo showed. It does not establish that every finding affects authenticated accounts. See the [source-based triage](../AUDIT_TRIAGE_2026-09-29.md) before using its priorities for normal application work. Several financial-number contradictions below come from demo-only responses.

Audit date: September 27, 2026 EDT / September 28, 2026 UTC.
Target: https://financial-planner-sand.vercel.app/investments
Method: manual browser navigation, clicks, form inspection, keyboard interactions, screenshots, and read-only DOM inspection of the deployed site. No source-code review or automated test suite was used to derive these findings.

## Scope and result

Reviewed Overview, Accounts, Transactions, Budget, Investments, Projections, Insights, all five Settings panels, global command search, light/dark Investments, and responsive layouts. Viewports: 1280×720 desktop, 768×1024 tablet, 390×844 mobile, and 320×740 narrow mobile. Every primary route was visited; this is a broad manual pass, not an exhaustive test of every possible input or workflow.

**31 findings: 3 high priority (P1), 17 medium priority (P2), and 11 low priority (P3).** Findings apply to the deployed demo. They do not establish that authenticated production behavior has the same defects.

P1 = major broken workflow or material data contradiction. P2 = significant usability, accessibility, or consistency issue. P3 = polish, wording, loading, or limited presentation issue.

## High-priority findings

### F01 · P1 · Accounts liabilities and net worth contradict the ledger and Overview

**Reproduce:** Enter demo → Accounts. Compare the totals, liability cards, and Overview.

**Observed:** Assets are $256,900. Rewards card is $1,250 and Student loan is $18,500, but Total liabilities and the Liabilities section total both show $0. Accounts net worth is $276,650. Overview net worth is $237,150.

**Expected:** The displayed debts total $19,750. Assets minus those liabilities equals $237,150. Accounts currently differs from Overview by $39,500. This is consistent with debt being added instead of subtracted somewhere, but the implementation cause was not inspected.

Adding a disposable $100 manual account changed Accounts net worth to $276,750 and Overview to $237,250, preserving the contradiction. [Evidence](02-accounts-incorrect-totals.png)

### F02 · P1 · All individual investment-history charts fail

**Reproduce:** Investments → select VTI, BND, or VT.

**Observed:** Each position shows “Couldn't load this position's history.” The aggregate investment chart works. VTI's “Try again” returned the same error. “Back to total” works.

**Expected:** Supply sample position histories in demo, or explicitly describe an intentional demo limitation instead of presenting a recoverable loading failure. [Evidence](01-investment-history-error.png)

### F03 · P1 · Rewards card planning details display the loan's values

**Reproduce:** Accounts → Planning details for Rewards card; then compare Student loan.

**Observed:** Both dialogs display 18500, 4.5%, 84, and 250. The card's account balance is $1,250; $18,500 is the Student loan balance. The Rewards card dialog also repeatedly describes a “loan.”

**Expected:** Show account-specific debt terms and credit-card wording. The identical values strongly suggest inappropriate shared sample details; no save was performed to assess downstream effects. [Evidence](03-debt-dialog.png)

## Medium-priority findings

| ID | Area and reproduction | Observation and expected behavior | Evidence |
| --- | --- | --- | --- |
| F04 | Transactions → search 95 | No matches, although the September ledger has two -$95 Cafe purchases. Searching Cafe finds both and totals $190. Search advertises merchant **or amount**; implement amount search or correct that promise. | [Screenshot](05-amount-search-no-results.png) |
| F05 | Accounts → debt planning dialog | Filled debt inputs have no visible persistent labels; DOM inspection exposes unnamed spinbuttons (only the APR field has the % suffix as its name). Values such as 18500, 84, and 250 do not explain their meaning. Add visible, associated labels and units. | [Screenshot](03-debt-dialog.png) |
| F06 | Accounts → investment planning dialog | Ticker, quantity, cost basis, position value, asset class, and date rely on placeholders or lack explanatory labels. Inspected ticker/date/quantity/basis/value fields have no associated label or aria-label. Use persistent labels, especially for the date and filled numeric values. Cash balance and contribution amount are better labeled. | [Screenshot](04-holdings-dialog.png) |
| F07 | Settings → Profile / Planning | Visible field captions are not associated with their inputs. Profile textboxes and Planning spinbuttons have no accessible name in the inspected DOM. Associate each caption with its field; visual proximity alone does not support screen-reader identification. | DOM inspection |
| F08 | Overview → Investment allocation | Shows target 80% equities, actual 91.1%, and “10 pp from target.” The displayed difference is 11.1 percentage points, or 11 if rounded to an integer. Derive the badge from the same holdings/target values. | [Screenshot](18-overview-allocation-drift.png) |
| F09 | Accounts → debt details → merchant-linked payment | The list described as outgoing transaction merchants includes Sample employer, whose sample transaction is +$7,200 income. Limit suggestions to eligible cleared outgoing payment activity, or explain broader matching semantics. | [Screenshot](03-debt-dialog.png) |
| F10 | Accounts → Sync all | The header sync is disabled in demo, but Accounts Sync all is enabled with zero linked institutions. Clicking it produces “Couldn't sync your linked institutions. Try again.” Apply consistent demo gating or provide an appropriate sample/manual refresh result. | Manually clicked; failure message observed |
| F11 | Projections → scenario chart | Description says the chart ends at each scenario's retirement age. The curves continue decades beyond the retirement markers, through 2087 on the axis. Correct the description or the plotted horizon. | [Screenshot](06-projections-chart-and-clipping.png) |
| F12 | Projections at 1280px → Scenario metrics | The right scenario column is clipped and requires horizontal scrolling despite only two scenarios. The metric labels wrap into narrow columns. Allocate more width or stack comparisons before reaching this layout. | [Screenshot](06-projections-chart-and-clipping.png) |
| F13 | Projections → Sensitivity analysis | +$2,890,164.74 overlaps “Illustrative demo calculation.” At 390px the same row contributes to page-level horizontal overflow: main width 375px, scroll width 391px. Its amount span is 64px wide but contains 109px of text. Allow wrapping or change the row layout. | [Screenshot](07-sensitivity-text-overlap.png); read-only DOM measurements |
| F14 | Investments at 768px | Search button text wraps into three lines and extends outside its short button/header area. Collapse to an icon earlier or prevent wrapping with an appropriate compact label. | [Screenshot](16-investments-tablet.png) |
| F15 | Investments at 390px → Positions | Account, cost basis, and gain/loss disappear entirely. There is no expandable row/detail alternative; selecting a position shows its value/error, not the missing data. Retain mobile access to those details. The help text still explains unavailable basis/gain-loss columns. | [Screenshot](12-investments-mobile-positions.png) |
| F16 | Transactions at 390px → Activity | The amount column is offscreen to the right. The initially visible ledger ends around Category, obscuring a primary transaction attribute. Horizontal scrolling exists, but prioritizing amount beside merchant would improve the mobile ledger. | [Screenshot](13-transactions-mobile-table.png) |
| F17 | Budget → Monthly plan | Every “If spending continues at this rate” estimate equals spending already recorded: Utilities $180 → $180; Housing $2,100 → $2,100; Groceries $480 → $480. The demo says data is through day 28 of September and describes extending spending across the full month. A straightforward 30/28 extrapolation would produce different values. Align demo estimates with the stated method or label them as fixed sample values. | [Screenshot](19-budget-pace.png); repeated DOM readings |
| F18 | Insights → emergency reserve recommendation | Recommends building six months of expenses with High confidence and +$1,200 annual impact. Sample expenses are $3,210/month, so six months is $19,260; Emergency savings is already $24,500. Settings reserve target is $24,000, also below savings. No explanation supports the recommendation or annual impact. Make sample advice coherent with sample finances or label it as a canned example. | [Screenshot](08-insights-demo.png); Accounts and Settings comparison |

| F30 | Global command search → type Everyday | Placeholder advertises accounts, but the existing Everyday checking account returns no results. Account-name search is not supported by the observed demo behavior. Implement advertised account search or narrow the placeholder. | [Screenshot](09-account-search-no-results.png) |
| F31 | Overview at 1280px → Investment allocation | The donut and legend do not fit the narrow right panel. Equity/bond percentage labels clip at the right edge, with horizontal overflow on the main content. Reflow the legend below the donut or adjust panel widths. Reproduced after the chart finished drawing. | [Screenshot](20-overview-allocation-clipped.png) |

## Low-priority findings

| ID | Area and reproduction | Observation and expected behavior | Evidence |
| --- | --- | --- | --- |
| F19 | Holdings dialog / transaction editor | UI exposes raw values such as equity, fixed_income, real_estate, expense, income, transfer, and contribution. Other surfaces use formatted labels. Show readable, consistently capitalized names. | [Holdings screenshot](04-holdings-dialog.png); transaction editor inspected |
| F20 | Add manual → Credit card; Edit Rewards card | APY (optional) appears on a credit-card account form. Debt APR is elsewhere. Tailor the form to account type so the relevant interest concept is clear. | Both forms inspected |
| F21 | First visit to Investments after entering demo | Before data arrives, shows 0 accounts, no holdings, “No investment accounts yet,” and instructions to unlink/relink accounts. It then replaces this with two accounts and three positions. Render a loading state rather than a misleading empty/error explanation. | Initial and subsequent DOM snapshots |
| F22 | Open the supplied Investments URL while signed out → Try demo | Demo starts on Overview instead of preserving the requested Investments destination. Preserve the return route after demo entry. Reproduced again in a fresh tab. | Navigation observed twice |
| F23 | Mobile global header | At 390px the Investments title becomes “Inves…” (Transactions and Projections similarly truncate). At 320px the title disappears and the account-link button is partially clipped at the right edge. Reduce secondary actions or use an overflow menu. | [390px](11-investments-mobile-top.png), [320px](15-investments-320-header.png) |
| F24 | Browser tab titles across routes | Main routes retain the generic “Meridian — Financial Planning Platform”; Settings uses “Settings — Meridian.” Use route-specific document titles consistently. | Tab listing and DOM alert titles inspected |
| F25 | Overview / Insights rule-based text | Amounts use $7200.00, $3210.00, and $3990.00 while cards/tables use thousands separators. Share the currency formatter with narrative text. | [Screenshot](08-insights-demo.png) |
| F26 | Insights initial recommendation count | “1 opportunities” should be “1 opportunity.” | [Screenshot](08-insights-demo.png) |
| F27 | Investments at 1280px → desktop Positions | Even with three positions, the table has a horizontal scrollbar; account and asset-type text wrap. Improve column widths or panel proportions to fit this common desktop width. | Visual inspection; mobile and other evidence corroborate column constraints |
| F28 | Projections scenario success | Both cards and the comparison table show “Unavailable” without a nearby reason or next step. The general illustrative-demo banner does not specifically explain unavailable Monte Carlo results. Label the intentional demo limitation, if that is the reason. | [Screenshot](06-projections-chart-and-clipping.png) |
| F29 | Overview / Accounts / Transactions copy in demo | Several labels refer to linked/connected accounts despite the demo explicitly showing 0 linked and 6 manual accounts. Accounts' empty institution prompt invites linking even though linking is disabled. Adjust copy for manual-only/demo state. | Accounts screenshot and route text |

## Additional design notes, not counted as bugs

- Investments has no account selector or time-range controls. The aggregate chart is useful, but individual account comparison and shorter-range exploration would improve it.
- Account cards under Investment accounts look informational and do not lead to account detail or planning. Consider a clear action if drilldown is intended.
- Four investment summary cards stack vertically on mobile, pushing the chart below the first screen. Budget already uses a compact two-column mobile summary layout; consider consistent treatment.
- Chart labels and “since Oct 28” omit the year even though the history crosses a year boundary. Hover does expose an ISO date.
- Dates use different conventions: account timestamps and manual transaction default use local September 27, while demo charts/as-of data and holding defaults use September 28. Review UTC versus local-day treatment; this audit does not establish a date-calculation bug.
- Demo identity uses a real-person-looking name/email rather than a clearly fictional demo persona. Consider a neutral sample identity; this is a presentation suggestion, not evidence of a data leak.

## Successful checks

- Aggregate investment chart, hover tooltip, portfolio sum, allocation percentages, known-basis gains, and Back to total worked. Holdings values sum to $224,000 and gains sum to $47,500.
- Light/dark switching worked on Investments and was returned to light.
- Mobile navigation drawer opened, closed, and navigated successfully.
- Merchant search and Housing category drilldown returned the expected transactions and totals.
- Transaction edit/manual-entry/CSV-review dialogs opened; their tabs and controls were inspected.
- Budget editing Housing from $2,200 to $1,000 correctly changed total budget to $2,850 and overall overspend to $360. It was restored to $2,200.
- Overview six-month selection updated period totals to $43,200 income, $19,260 expenses, and $23,940 net. Outlook and expense drilldown opened correctly.
- A $100 disposable demo manual account was created; both Overview balance and liquid assets rose by $100. The Accounts arithmetic error persisted.
- Projection sliders changed calculated balances after updates settled; the future-dollar toggle changed the displayed scenario values. No stale-slider bug is claimed.
- Debt payoff Calculate produced an explicitly illustrative sample result. This is not validation of its financial math.
- Insights refresh and Mark as done worked; completing the recommendation reduced the count and combined impact to zero.
- Profile, Planning, Institutions, Archived accounts, and Notifications panels opened. Notifications were visibly disabled with Coming soon copy.
- Command navigation/search worked for commands. Account-name search failed as recorded in F30. Link a new account navigated to Accounts but did not open a link flow in demo.

## Limits and cleanup

Bank connections, Gemini, and delivery of notifications were disabled, so their real integrations were not tested. CSV upload/import, exports' file contents, permanent deletion, scenario deletion, and authenticated-account workflows were not exercised. A keyboard/screen-reader audit and measured color-contrast audit were not performed.

The browser stalled when testing archive of the disposable demo account. The supported dialog check did not produce a recoverable dialog, so archive/restore remains **inconclusive**; no product defect is asserted from the control timeout. The test tab was closed, and a fresh demo tab verified the original six-account baseline. Temporary responsive overrides were reset. No application code or real financial data was changed.

Screenshots are in this directory. Start fixes with F01–F03, then amount search, labels, responsive layout, and data-derived demo copy.
