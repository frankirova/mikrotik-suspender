# Changelog

## [0.1.0] - 2026-11-10

- Added immutable, content-addressed plans and explicit confirmed apply.
- Made planning strictly read-only and guaranteed connection cleanup.
- Added CSV/IP/CIDR/date/duplicate/limit validation with line errors.
- Added RouterOS aliases, verified TLS defaults, timeouts and post-write checks.
- Added per-action partial-failure reports, API/CLI JSON and meaningful health.
- Added package metadata, CI, hardened Docker defaults and security guidance.
- Added a demo screencast and recording pipeline, captured against a real CHR.
- Fixed the saved-options card getting stuck on "loading" when API_KEY is set
  and the token is typed after the page loads.

Verified on RouterOS 7.24.6 (CHR): planning is read-only and confirmed apply
produced and verified the expected address-list. No RouterOS 6 or other-hardware
claim is made without equivalent real-device evidence.
