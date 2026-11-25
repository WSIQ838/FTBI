# Institution settings, imports and preferences

## Branding

The Institution Administration role manages the portal name, short name, accent color, header color and logo. Custom colors must use six-digit hex values and meet a 4.5:1 contrast check against their supported light backgrounds; dark-mode links retain the tested light accent. Logos are public on the login page. Uploads require the malware scanner, PNG/JPEG validation, a 512 KB limit and a maximum of 2048 pixels per side. Accepted logos are re-encoded as PNG without original metadata. Save the institution settings before uploading a logo.

New transcript, diploma and enrollment-letter snapshots capture the configured institution name. Existing snapshots retain their recorded name. Legacy transcripts without an institution snapshot retain the environment-name fallback. Branding is not an institutional policy approval workflow, and the logo is not a credential signature.

## Bulk imports

Registrars with student-profile creation permission can import students from existing active, nonstaff user accounts. Academic administrators with course creation permission can import course sections. Imports never overwrite existing records; course imports are always unpublished. Identity provisioning and student credential distribution remain separate controlled processes.

The upload page specifies the required CSV columns and their order. Files must be UTF-8, no larger than 2 MB, and contain at most 1000 data rows. All referenced programs, departments, terms and accounts must already exist. Student numbers, usernames and course section identities must be unique. Each row receives model validation.

Uploading creates a private preview belonging to the submitting operator. It does not create student/course records. Review the complete preview and choose Commit. Previews expire after 24 hours. The service checks the preview digest and validates the current database again, then commits all rows in one transaction. Any validation error or database conflict leaves the whole import uncommitted. Repeating a successfully committed request returns the same result without adding duplicates. Preview and commit events are audited. Preview payload retention still needs an approved institutional policy.

## Personal preferences and search

Portal preferences allow users to select an IANA timezone, hide/show the course and services dashboard sections, and sort courses by code, title or newest term. The sidebar remains available when dashboard sections are hidden. Dates continue to be stored as timezone-aware values; display and date/time form interpretation use the selected timezone shown in the footer. Preferences are private to the account, and timezone activation is cleared after each request.

Search adds term, department, content-type and assignment-due-date filters. Available filters and results stay within courses visible to the user; locked lesson content remains excluded. This is not a global student-record search or a configurable report builder. Localization and broader usability acceptance remain outstanding.

Regression tests cover import preview/commit/replay, stale-data rollback, duplicate detection, expiry, operator isolation, contrast rejection, mocked scanner/logo validation, timezone isolation, dashboard controls and filtered search privacy. The browser suite exercises preferences and keyboard/accessibility behavior in five configurations. Live institutional branding approval and real-device/screen-reader acceptance are separate.
