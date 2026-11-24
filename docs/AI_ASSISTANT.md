# Academic assistant and governance

The assistant provides study tutoring, faculty drafting and administrative guidance through a fixed HTTPS OpenAI Responses endpoint. It never receives database tools or automatically changes grades, eligibility, finances or student records. Provider redirects are rejected. Prompts and answers are not retained by FTBI; the request uses `store=false`. This setting does not establish a provider retention agreement or guarantee that users will not enter personal information. Every request requires the user's privacy consent.

Both environment-level provider configuration and an enabled institutional AI configuration are required. The AI Administration dashboard records a policy approval reference, monthly budget, approved input/output prices for the configured model, output-token cap and per-user hourly quota. API keys remain outside the database and dashboard. Enabling the dashboard requires positive prices, a positive budget and a policy reference; entering a reference is not evidence that approval has actually occurred.

## Retrieval

Authorized administrators maintain approved plain-text knowledge documents with learner, faculty or administrative audiences. Retrieval ranks keyword matches among approved documents available to the selected, authorized mode and supplies up to three excerpts. Unapproved and role-inaccessible documents are excluded. Source titles are shown with the answer. Documents are treated as untrusted reference material, not instructions. This is bounded local text retrieval, not PDF ingestion, semantic embeddings or access to personal student files. Review all knowledge documents before approval.

## Usage and budgets

The database serializes budget reservations before provider calls. A conservative UTF-8 input-byte estimate plus protocol allowance and the maximum output-token count determine the reservation at the configured prices. Successful calls settle using reported input/output token counts. Failed or ambiguous calls retain the full reservation because provider billing is unknown. Invalid usage or a cost exceeding the reservation disables AI pending review. Hourly quotas include failed/reserved requests.

The usage dashboard stores user, mode, model, status, token totals and cost metadata without prompt/answer text. It highlights failures/anomalies and blocked request counts. Cost figures are estimates at institution-entered prices, not imported invoices; pricing changes, provider surcharges, project-wide billing and any other applications sharing a provider account remain outside this local control. Configure provider-side limits and reconcile invoices before acceptance.

Live provider validation, model-specific price approval, academic-integrity review, privacy review and institutional AI policy approval remain release blockers. Tests mock provider responses and verify permission boundaries, retrieval audiences, budget rejection, idempotent settlement and failure behavior.
