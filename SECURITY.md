# Security Policy

## Supported versions

Only the latest `0.1.x` release receives security fixes while the project remains
pre-1.0. No release has yet been validated on real RouterOS hardware.

## Reporting

Report vulnerabilities privately through GitHub Security Advisories for this
repository. Do not include production credentials, customer names, routable
addresses, RouterOS exports or packet captures. Allow maintainers time to assess
and coordinate a fix before public disclosure.

## Operational boundaries

Use TLS verification, target aliases, a dedicated least-privilege RouterOS user,
source-restricted RouterOS services and API authentication. Logs intentionally
record action counts/types and error classes, not passwords, tokens, customer
names or full input rows. RouterOS and reverse-proxy logs remain operator-owned.
