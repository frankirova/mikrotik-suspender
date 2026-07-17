# Contributing

Use Python 3.11+, create a virtual environment and install `.[dev]`. Keep each
change as one reviewable behavior with its tests and user-facing documentation.
Run the commands in the README before requesting review.

Never use a production router for tests. Adapter tests must use fakes or recorded,
redacted response shapes. A real CHR lab must be isolated and explicitly opt-in;
document RouterOS version, configuration boundary and exact evidence without
claiming broader compatibility.

Security changes must preserve read-only planning, verified plan identity,
allowlisted router aliases, fail-closed non-loopback auth and secret-free output.
