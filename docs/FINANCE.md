# Finance manual

Authorized staff use Finance billing. Students use Invoices and payment plans or Payments. Finance permissions must include the new invoice, allocation, plan and tuition-schedule models; institutional role provisioning includes these permissions. Staff status alone does not grant access.

## Invoices and tuition

Issue invoice creates an immutable invoice and matching released ledger charge in one transaction. Activate an approved tuition schedule for a program and term in Administration. Billing creates one tuition invoice per active enrollment using course credits and the approved per-credit rate, plus one term fee per student. The billing command is idempotent: rerunning does not charge the same enrollment or fee again. Schedule changes do not rewrite issued invoices; add/drop refunds and billing adjustments need finance review. An independent, approved financial-hold policy can now restrict new registrations; see below.

## Verified payments and installments

Student-submitted references are claims awaiting review. Confirm funds independently, then use Confirm funds received and credit ledger. This creates one ledger credit and records the reviewer atomically; retries cannot create duplicate credits. Processor-managed records can only be verified through signed Stripe events. Generic admin payment status edits are disabled.

Before allocating payments, approve a plan with up to 24 dated installments totaling the full invoice. Allocate only verified payments belonging to the invoice's student. The system prevents invoice overpayment, overspending a payment and duplicate form replay. Allocations reduce the invoice balance without adding another ledger credit. Payments apply to installments in due-date order. Plans cannot be rewritten after approval; corrections require an explicit future adjustment workflow.

Online checkout accepts a partial amount of at least USD 1 up to the released account balance. It reuses the student's pending checkout and blocks a conflicting amount. Completed or expired checkout outcomes require reconciliation; no second charge is silently created. Live Stripe test-mode validation is still required. Verified receipts are downloadable PDFs available only to their owner or permitted finance staff.

## Reconciliation and limits

The private CSV reports each student's released ledger balance, invoice charges, verified payments, allocations, unallocated payments and net account credit. This supports internal reconciliation; it does not fetch processor settlements or bank statements. Existing verified records from before the ledger-link migration may have no explicit link and require historical reconciliation. Manual-payment refunds and disputes now have controlled posting workflows below. Live processor refund/dispute reconciliation, accounting integration and full scholarship workflows remain outstanding. Never treat an unallocated payment as a new ledger credit or invent successful provider reconciliation.

## Confirmed refunds and disputes

Payment adjustments and disputes shows verified payments and net remaining funds. Authorized finance staff may record an already completed refund of a manual payment, or a confirmed withholding of funds that opens a dispute. The action requires a unique external evidence reference, a reason and an explicit confirmation. It does not transfer money, initiate a refund or contact a bank. Never enter bank credentials or full card details. Processor-managed payments are rejected by these manual posting routes; their provider integration remains unfinished.

Adjustments append ledger entries and preserve the original payment and allocation records. Refunds and withheld funds consume unallocated credit first, then release allocations in reverse allocation order. Invoice and installment balances reflect these releases. The total reversed principal cannot exceed the remaining payment, even under concurrent requests. Finance must review the allocation consequences; returned tuition is not automatically waived. A fee waiver or tuition charge correction requires a separate authorized adjustment workflow, which is not yet provided here.

Open disputes block further allocations and refunds from the affected payment. Record a final lost outcome only when confirmed: it does not debit the student twice. A won outcome requires evidence that funds were actually restored; it appends one credit. Recovered funds remain unallocated until finance reallocates them. Final outcomes cannot be overwritten through the portal. Processor fees, partial dispute settlements and appeals/reopening are not yet modeled. Internal reference/reason text is restricted to finance; students see adjustment amounts and dispute status.

Receipts show the original payment and its current net amount. Reconciliation exports now include reversed/withheld principal, recovered funds, effective allocations and net payments, with two decimal places. Historical records lacking a linked ledger entry must be reconciled before adjustments. Recording evidence is not proof of bank settlement, and live-service acceptance remains open.

## Automatic financial registration holds

FinancialHoldPolicy is a singleton, disabled by default. Enabling it requires an institutional approval reference, overdue threshold and grace days. Evaluation totals unpaid overdue invoice amounts, or only overdue installments when a plan exists. It deducts unapplied account credit (total outstanding invoices minus the released ledger balance, when positive) from overdue obligations before considering future obligations. Unallocated payments and other released credits therefore protect the account. Other released charges consume credit. An invoice/installment becomes overdue after its due date plus grace days. Amounts at or above the threshold activate the hold.

Evaluation runs during new registration and waitlist promotion, and through the finance action or evaluate_financial_holds command. Scheduling that command and monitoring it on institutional infrastructure remain deployment gates. Disabling the policy releases automatic holds on the next evaluation. Placement/release generates an audit event and a durable private notification. The payment history shows the last evaluated status and timestamp. Manual registration holds remain independent and are never cleared by this policy. Existing enrollments are not removed, and the policy does not restrict learning access or official records. Institutional notice, appeal and hardship procedures require acceptance; there is no automatic dismissal.

## Validation limits

academics.test_finance_adjustments covers partial refunds, allocation release, duplicate requests, over-refund protection, manual/processor separation, won/lost disputes, privacy, hold approval/defaults, installments, grace periods and registration enforcement. A PostgreSQL concurrency test verifies simultaneous refunds cannot exceed the original payment. These tests use synthetic external evidence; no real refund, dispute or bank operation has been performed.

Provider integration references reviewed: [Stripe refund creation](https://docs.stripe.com/api/refunds/create), [refund lifecycle](https://docs.stripe.com/refunds), [dispute API](https://docs.stripe.com/disputes/api). The manual posting workflow does not claim to implement those live operations.
