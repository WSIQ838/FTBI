# Institutional policy governance and voluntary demographics

Policy Authors maintain policy identities and propose immutable versions. Policy Reviewers independently approve or reject them with a reason and an institutional authority reference. Staff membership alone is insufficient. Authors cannot approve their own versions, even if they also hold reviewer permission. Each decision is retained once; different decisions require a new version. Concurrent proposals receive distinct version numbers.

Policy versions preserve title, complete text, configuration, author and effective/expiry dates. Code and kind cannot be changed through administration after a version exists. The current version is the highest approved version whose effective date has arrived. An expired or withdrawn current version does not silently reactivate an older version. Future approved versions do not take effect early. Withdrawal preserves evidence and requires an authorized reviewer and a reason. Policy acknowledgment records a user's acknowledgment of one currently effective version; it is not demographic consent or proof of legal acceptance.

Academic, finance, privacy, security and institutional policy versions are governance documents. Their text does not automatically modify grading, fees, holds, AI, retention or other application settings. Those remain explicit separate controls. This registry supports review and history; no real institutional policy has been supplied or approved by this development work. Legal applicability, institutional authority, notices and external security/privacy acceptance remain release gates.

## Optional demographic collection

Demographic Administration controls a singleton collection setting, disabled by default. Enabling it requires a currently effective, independently approved policy of kind demographics. The question configuration is part of the immutable reviewed version, so choices cannot be changed behind an approved policy. Allowed question keys are age_band, gender, first_generation and residency_country. Configure one to four voluntary choice questions; each has a label and 2–250 unique coded choices, including prefer_not. Questions always permit leaving an answer blank. There are no free-text response fields and no inferred demographics.

The policy configuration schema is:

```json
{"questions":[{"key":"first_generation","label":"First-generation college student?","choices":[{"code":"yes","label":"Yes"},{"code":"no","label":"No"},{"code":"prefer_not","label":"Prefer not to answer"}]}]}
```

This is a synthetic schema example, not an approved institutional definition. Labels, country lists and criteria require actual institutional review. Policy text must explain purpose, access, retention, withdrawal and contact procedures before collection is enabled. Configuration must contain only the questions key; question objects require key/label/choices and choice objects require code/label. Codes use 1–30 lowercase letters, digits or underscores. Submission rejects unknown questions and choices.

Students see the complete current policy before giving separate affirmative consent. They can omit any question, update their current response or delete all current demographic answers. Current answers are stored once per student with the exact policy version and consent time; prior answer history is not retained in application tables. Answers under an older policy are not automatically reused or counted under a new version. Policy changes during submission require renewed review. Disabling collection, policy expiry or withdrawal stops collection and reporting, but does not silently delete previously collected answers. Students can still withdraw while collection is off.

Answers are not used for admissions, grades, scholarship eligibility, registration or learning access. There is no generic administration view of individual demographic responses. Students access only their own response. Audit entries record save/withdraw actions without answers. Database operators and backups remain privileged infrastructure and require separate controls; deletion from current tables does not erase existing backups. Approved retention and backup-erasure handling remain unfinished release requirements.

## Restricted aggregate reporting

Demographic Reporting is a separate explicit permission; president/dean roles do not receive it automatically. Reports count voluntary responses only under the currently enabled effective policy. No department/campus filters, individual rows or export endpoint are provided. Each question's entire result and total are withheld if any nonzero response category contains fewer than five responses. Empty categories may be shown as zero when all nonzero cells meet the threshold. Missing answers are not assigned a demographic category.

This minimum-cell rule is a risk reduction, not a deidentification guarantee. Repeated queries, outside knowledge and linked datasets still need institutional privacy review. No public or external disclosure is authorized. Reports are recalculated after a student withdraws; immutable demographic reporting snapshots are intentionally not created.

## Verification

academics.test_governance tests draft privacy, independent review, decision replay, immutable versions, future/expired/withdrawn policy behavior, acknowledgments versus consent, question schema validation, disabled collection, stale-policy submissions, restricted aggregate access, whole-question suppression and student withdrawal. PostgreSQL concurrency coverage verifies distinct policy version allocation. Tests use synthetic policies and responses; they do not establish institutional privacy or FERPA acceptance.
