# HTTP interfaces and data exchange

FTBI currently exposes a session-authenticated HTML application, private file exports, operational health responses and a signed Stripe webhook. It does not provide a general versioned REST API, OAuth API scopes, OpenAPI contract or public student-record endpoint. Routes in `ftbi/urls.py` and their view authorization are authoritative. This is documentation of implemented interfaces, not production integration acceptance.

## Authentication and errors

Portal actions require a logged-in account and any applicable MFA, role, ownership or enrollment checks. Browser POST forms use Django CSRF protection. Successful form actions normally redirect; validation failures usually render HTML. Missing login can redirect to login, while denied or absent resources can return 403 or 404. Do not interpret an HTML login page as a successful JSON response. No universal JSON error envelope or pagination contract exists. Client automation must preserve access controls and must not use a superuser account to bypass them.

Only the Stripe webhook is exempted from browser CSRF protection; it instead validates the provider signature over the original request bytes. Monitoring uses a separate private bearer token. Portal exports contain sensitive records and must remain in approved storage.

## JSON and health interfaces

| Route and intended method | Authentication/scope | Response and behavior |
| --- | --- | --- |
| GET or HEAD `/health/live/` | No portal session | 200 JSON with `status: ok`; process liveness only. |
| GET or HEAD `/health/ready/` | No portal session | 200 `status: ready` after database/cache probes; 503 `status: unavailable` on failure. It does not establish all release gates. |
| GET or HEAD `/health/metrics/` | `Authorization: Bearer <private monitoring token>` | 404 when unconfigured; 401 for absent/wrong authorization; 200 for healthy checks or 503 for any failed check. JSON contains `healthy`, `checked_at`, `checks` and `metrics`. Query-string credentials are unsupported. See OBSERVABILITY.md. |
| GET `/faculty/<course-id>/export.json` | Assigned instructor | Private no-store `ftbi-course` version 2 package containing authored learning/communication content. No student records. See LEARNING.md for exact coverage, author-text privacy and exclusions. |
| GET `/account/records.json` | Current user's student profile | Private no-store `ftbi-personal-record-v1` download. Top-level fields: `format`, `exported_at`, `account`, `student`, `enrollments`, `released_grades`, `released_ledger`, `submissions`, `emergency_contacts`, `status_history`, `scope_notice`. Attachments, private staff notes and audit logs are excluded. |

Dates/datetimes and decimal values use Django JSON serialization; consumers must not assume decimal money/GPA values are floating-point numbers. Course exports retain explicit timezone offsets. File schemas are versioned independently of application release tags.

Course import is a multipart browser POST to `/faculty/<course-id>/import/`, with `file` and optional integer `shift_days` in -365..365. Version 1 and 2 packages are accepted, with a 2 MB file limit, bounded nesting/lists and strict fields/references. Target ownership, emptiness and unpublished state are enforced. Dates must be offset-aware; invalid shifts, cycles and late validation failures roll back the complete import. Errors render the import form rather than a JSON error object.

## Payment callback

`POST /payments/webhook/` is disabled with 404 unless Stripe is enabled. Supply the original JSON body and `Stripe-Signature` header; do not reserialize before signature verification. Invalid JSON/signature or missing/unknown/mismatched payment references return 400. Only paid `checkout.session.completed` events can credit the ledger. Other signed event types and unpaid completions return 200 without a credit.

The handler compares `metadata.ftbi_payment_id`, session ID, USD currency and integer `amount_total` with the existing payment request. An initializing request returns 503 for a retry; a non-pending/non-verified conflicting state returns 409. A verified matching replay returns 200 without a second credit. The student/payment lock, ledger posting, audit and notice are transactional. A 200 for an unrelated event does not mean that event's business workflow is supported. Refund/dispute initiation and reconciliation, asynchronous methods and live provider acceptance remain incomplete.

The portal's CSRF-protected `POST /payments/checkout/` accepts optional decimal `amount`, at least USD 1 and no greater than the eligible balance. It redirects to provider checkout; invalid input returns 400, ineligible balance 403, pending-session conflicts 409 and provider failures 503. See STRIPE.md and FINANCE.md before any approved integration testing. No live charges should be used for training.

## Other exchange surfaces

CSV downloads include financial reconciliation, admission conversions, institutional summaries and scoped reporting exports. Their permission scopes differ; access to one does not grant another. Reviewed report snapshots require the independent approval workflow before export. See [finance](FINANCE.md), [admissions](ADMISSION_LIFECYCLE.md) and [institutional reporting](INSTITUTIONAL_REPORTING.md).

`GET /calendar/export.ics` is a private snapshot of up to 1,000 visible published events, not a public subscription feed. Credential PDFs and document versions use private routes with ownership/role checks; knowing an identifier alone does not authorize a download. Public credential verification uses its separate identifier-and-code form and optional exact-file comparison, not a public records API. See [credentials](CREDENTIALS.md) and [uploads](UPLOAD_SECURITY.md).

No API key should be embedded in a URL or shared training artifact. Rate limits, reverse-proxy acceptance, external identity/provider agreements, comprehensive endpoint contracts and an independent authorization review remain open release work.

## Private file archive

CSRF-protected `POST /account/files.zip` returns an attachment ZIP with `private, no-store` caching. It packages only the current user’s owned and accessible document versions, coursework attachments/revisions and unrevoked stored credentials. `manifest.json` uses format `ftbi-personal-files-v1` and records generated safe paths, original names, byte counts and SHA-256 digests. Original filenames never become archive paths. Limits are 500 files and 50 MB of file bytes; integrity/size failures return 403 without a partial archive. A repeated request within 60 seconds returns 429 and `Retry-After: 60`; a shared production cache is required for cross-worker enforcement. GET is not supported. This does not include private staff notes, audit logs, dynamically generated letters/course certificates or all data needed for a reviewed records request.
