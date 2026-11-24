# Finance manual

Authorized staff use Finance billing. Students use Invoices and payment plans or Payments. Finance permissions must include the new invoice, allocation, plan and tuition-schedule models; institutional role provisioning includes these permissions. Staff status alone does not grant access.

## Invoices and tuition

Issue invoice creates an immutable invoice and matching released ledger charge in one transaction. Activate an approved tuition schedule for a program and term in Administration. Billing creates one tuition invoice per active enrollment using course credits and the approved per-credit rate, plus one term fee per student. The billing command is idempotent: rerunning does not charge the same enrollment or fee again. Schedule changes do not rewrite issued invoices; add/drop refunds and billing adjustments need finance review. There is no automatic financial-hold policy yet.

## Verified payments and installments

Student-submitted references are claims awaiting review. Confirm funds independently, then use Confirm funds received and credit ledger. This creates one ledger credit and records the reviewer atomically; retries cannot create duplicate credits. Processor-managed records can only be verified through signed Stripe events. Generic admin payment status edits are disabled.

Before allocating payments, approve a plan with up to 24 dated installments totaling the full invoice. Allocate only verified payments belonging to the invoice's student. The system prevents invoice overpayment, overspending a payment and duplicate form replay. Allocations reduce the invoice balance without adding another ledger credit. Payments apply to installments in due-date order. Plans cannot be rewritten after approval; corrections require an explicit future adjustment workflow.

Online checkout accepts a partial amount of at least USD 1 up to the released account balance. It reuses the student's pending checkout and blocks a conflicting amount. Completed or expired checkout outcomes require reconciliation; no second charge is silently created. Live Stripe test-mode validation is still required. Verified receipts are downloadable PDFs available only to their owner or permitted finance staff.

## Reconciliation and limits

The private CSV reports each student's released ledger balance, invoice charges, verified payments, allocations, unallocated payments and net account credit. This supports internal reconciliation; it does not fetch processor settlements or bank statements. Existing verified records from before the ledger-link migration may have no explicit link and require historical reconciliation. Refunds, disputes, chargebacks, accounting integration and full scholarship workflows remain outstanding. Never treat an unallocated payment as a new ledger credit or invent successful provider reconciliation.
