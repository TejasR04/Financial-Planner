# Functional review — September 25, 2026

The codebase was reviewed in four functional areas by Luna agents. This review focused on new, user-visible defects after the September 17 audit and September 19 repair review. Findings were checked by the coordinator before fixes were assigned. No production data or live bank connection was changed.

| Functional area | Requirement checked | Finding | Decision |
| --- | --- | --- | --- |
| Accounts, debt, sync | Scheduled manual-loan reductions and APR continue when the app is closed | Background financial sync skipped loan automation when no interactive request occurred, including when Plaid was not configured | Fix |
| Accounts, debt, sync | Historical cleared payments remain reflected in a manual loan | Archiving the payment's source account reversed the saved loan reduction | Fix |
| Accounts, debt, sync | A multi-bank sync dates loan interest against all incoming payments | Loan automation ran after each bank, so a payment from a later bank could arrive after interest had already accrued through today | Fix: apply after all institution patches |
| Transactions, CSV, budgets | CSV imports preserve signed refunds | Explicit expense typing forced positive refunds to negative spending | Fix |
| Transactions, CSV, budgets | Reimporting a changed export does not duplicate saved purchases | CSV identity used physical line numbers; inserted or reordered rows could replay saved transactions | Fix, with conservative compatibility for old identities |
| Investments, projections | Valid ticker symbols are stored for automatic pricing | Whitespace-only symbols passed creation validation; updates did not normalize symbols | Fix |
| Investments, projections | Quick retirement controls accept valid ages | Age 80+ users could get an invalid slider range and failed projection | Fix; age 94+ is explicitly unsupported by the quick model's age-95 horizon |
| Onboarding, auth, assistant | Onboarding accurately reports the save result | Two independently committed profile requests could partially succeed while the UI reported total failure | Fix |
| Investments, projections | Monthly contributions run without the app open | Initial candidate was incorrect: background financial sync already applies them | No change |

The preceding manual-loan review also added daily APR accrual, same-day merchant payment eligibility, and CSV loan-rule application. Its database migration is `a9c0d1e2f3b4_add_loan_interest_checkpoint.py`; existing balances begin accruing from their first checkpoint because no historical principal baseline is available.

CSV imports cannot always identify which of several byte-for-byte identical purchases was previously imported under the older line-number scheme. The compatibility fallback preserves the imported count conservatively; a genuinely separate purchase may require explicit confirmation in preview.

Validation: 281 backend and 83 frontend unit tests, Ruff, ESLint, TypeScript, and backend mypy passed. Alembic reports a single head at `a9c0d1e2f3b4`. PostgreSQL integration tests were not run because `TEST_DATABASE_URL` is not configured in this workspace. A standalone single-bank sync still updates loans immediately; a later payment from a different bank can therefore arrive after an earlier interest checkpoint.
