# Scholarship administration

Scholarship Administration permissions control funds, review and account posting. Staff membership alone grants no access. Funds specify a term, optional program restriction, application window, total budget, per-award cap, optional minimum GPA and earned credits. Publishing requires an institutional approval reference. Budgets cannot be reduced below approved and posted commitments.

Students use Scholarships to see open funds, eligibility and private applications. Each student submits once per fund and term. GPA and credits use released grades from completed terms; an absent GPA cannot meet a configured minimum. Eligibility is captured at submission and recalculated at approval. Meeting minimums does not guarantee an award. Staff review the statement and published criteria. Do not request medical evidence, bank credentials or full card details in statements.

An authorized officer approves a positive amount no greater than the request, current award cap and remaining budget. Concurrent approvals serialize against the fund. Self-approval is prohibited. Approval reserves funds and creates a visible financial-aid record but does not change the ledger. Applicants may withdraw pending applications. Declines and withdrawals retain history.

Post account credit applies an approved award to the student's institutional account once. This is a tuition-account credit, not an external bank transfer. Cancel releases an unposted commitment. Reverse appends an offsetting debit for a posted award and releases its budget; the original credit remains. Reasons and action history are visible to the student. Coordinate policy, notice and appeals before a reversal. Generic administration cannot edit linked aid awards or their ledger entries.

Renewals require the student's own posted award from an earlier term with the same fund code. A renewal is a new application requiring fresh eligibility review and available budget; it is never automatically approved. Approval snapshots retain the fund wording, criteria, GPA, credits, limits and decision reason. Later fund edits do not rewrite them.

This workflow does not implement external aid disbursement, donor accounting, statutory aid reporting, financial-need assessment, document collection, automatic renewals or a formal appeals process. Institutional scholarship criteria and accounting/privacy acceptance remain outstanding. Historical manually entered FinancialAidAward records are not automatically linked or credited.

Validation: six scholarship integration tests cover private access, review permissions, eligibility changes, self-approval prevention, budget limits, immutable approval snapshots, once-only posting/reversal, cancellation and renewals. PostgreSQL concurrency coverage verifies two approvals cannot exceed one shared budget. Synthetic records only; no money was transferred.
