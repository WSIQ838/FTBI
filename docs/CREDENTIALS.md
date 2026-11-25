# Credential lifecycle and verification

New transcript and diploma issuance finalizes one exact PDF, an academic snapshot, a SHA-256 digest and a private verification code. Later downloads return those same bytes. The academic record and template text are captured at issuance; later edits do not rewrite issued documents. Students see their own credentials; authorized registrars can inspect the credential registry.

## Registrar actions

Use Academic credentials to finalize an existing issued record, revoke a credential with a reason, or replace a revoked credential. Finalizing an old record is an explicit staff action; migration does not invent signatures for historical documents. Revocation preserves the evidence and blocks further portal downloads. Copies already downloaded remain outside the portal's control and must be checked against current registry status. Repeated replacement submissions return the existing replacement instead of issuing duplicates.

A replacement preserves the original academic snapshot and template, receives a new identifier and verification code, and uses the current signing policy. It does not correct grades or names. Academic corrections require a reviewed record correction and a new issuance workflow. The original remains revoked. Registry revocation is distinct from certificate revocation.

Credential templates in administration accept plain heading, body and footer text with these placeholders: {recipient}, {program}, {institution}, {issued_date}, {identifier}. An enabled template requires an approval reference. Formatting expressions, attribute access and HTML are not supported. Review institutional wording before enabling a template. Long transcripts paginate with repeated table headings and page identifiers.

## Holder and recipient verification

Students download finalized PDFs from Academic credentials. Share the credential ID and verification code only with the intended recipient. The public verification portal requires both values and does not return names, student numbers, grades or PDF downloads. An optional PDF upload is hashed to compare it with the exact finalized file; its contents are not parsed or retained by the application. File comparison is limited to 10 MB. Verification requests are rate limited by client address.

An active registry record alone does not authenticate a file. A matching file digest establishes that the submitted bytes match the institution's stored artifact. A digital signature additionally needs independent certificate-chain trust validation. The portal labels these results separately and shows revoked status even when the submitted file matches.

## Signing policy and outstanding acceptance

Signing is disabled by default; unsigned artifacts are explicitly labelled. The application reads FTBI_CREDENTIAL_SIGNING_REQUIRED, FTBI_SIGNING_P12_PATH and FTBI_SIGNING_P12_PASSWORD. Required signing fails closed: missing, unusable, expired or unsuitable signing material prevents issuance and rolls back its database changes. It never silently substitutes an unsigned credential. Signing uses an encrypted PKCS#12 certificate/key, SHA-256 and an embedded PDF signature. Keys and passwords must not enter source control, logs, browser forms or demonstration data.

No institutional signing certificate, production secret mount or key custodian has been supplied. The existing production Compose definition does not provision signing material. Institutional certificate trust, protected key custody and rotation, document-signing policy, recipient validation, and security acceptance are external release gates. The implementation does not yet provide HSM integration, a trusted timestamp service or embedded long-term revocation validation evidence. It makes no claim of PDF archival-signature compliance or accreditation. Third-party transcript delivery remains unfinished.

## Evidence

academics.test_credentials covers private access, exact-byte downloads, verification mismatch and privacy, revocation, replacement replay, immutable snapshots/templates and issuance rollback. It generates an ephemeral self-signed certificate and validates actual transcript and diploma signatures against that explicitly trusted test root, then detects a modified PDF. This is cryptographic integration coverage, not acceptance of a real institutional certificate. Synthetic multipage transcript and diploma PDFs were rendered and visually checked. No production records or keys were used.
