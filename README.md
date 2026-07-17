# MikroTik Suspender

Release candidate for `v0.1.0`. It reconciles a validated CSV into one RouterOS
address-list through an explicit, read-only plan and confirmed apply workflow.

> This software has only automated adapter-contract coverage. It has not been
> verified against real RouterOS 6 or 7 hardware. Test in an isolated CHR lab
> before production use.

## Safety model

- Router targets and their address-lists are explicit aliases from `ROUTERS_JSON`;
  requests cannot supply either value.
- Planning reads RouterOS and never calls add/set operations.
- Plans are immutable and content-addressed. Apply rejects modified plans,
  another router, changed RouterOS state, unknown plans and unconfirmed requests.
- TLS with certificate and hostname verification is the default. Plaintext or
  unverified TLS requires explicit configuration and emits a critical warning.
- Every write is read back. Results are per action, so a partial failure can be
  safely reconciled by creating a fresh plan.
- Managed comments have one deterministic suffix and never accumulate dates.
- Binding beyond loopback without `API_KEY` fails at application startup.

An address-list does not block traffic by itself. RouterOS must have a firewall
rule that consumes the configured `src-address-list` or `dst-address-list`.
The correct chain and direction depend on your network; this tool does not create
that rule.

## Install

Python 3.11 or newer:

```bash
python -m venv .venv
. .venv/bin/activate
pip install .
```

For contributors, use `pip install -e '.[dev]'`. Runtime dependencies and the
`v0.1.0` version are canonical in `pyproject.toml`; dev tools are exact-pinned.

## Configure

```ini
USER_MIKROTIK=suspender
PASS_MIKROTIK=replace-me
ROUTERS_JSON={"lab":{"host":"192.0.2.10","port":8729,"address_list":"lab-suspensions"}}
ROUTER_TLS=true
ROUTER_TLS_VERIFY=true
ROUTER_TIMEOUT=10
API_KEY=generate-a-long-random-value
HOST=127.0.0.1
CSV_PATH=./data/clientes.csv
MAX_ENTRIES=1000
```

The RouterOS certificate must validate for the configured host. For a private CA,
install that CA in the container/host trust store. `ROUTER_TLS=false` or
`ROUTER_TLS_VERIFY=false` is an insecure, opt-in laboratory escape hatch.

Use a dedicated RouterOS group/user with only API login and the minimum policy
needed to read and modify `/ip/firewall/address-list`. Restrict the `api-ssl`
service source address in `/ip service`; disable the plaintext `api` service when
unused. Do not use the `admin` account.

CSV format:

```csv
ip,nombre
10.0.0.10,Customer A
10.0.1.0/24,Customer network
```

Invalid or missing values, duplicate addresses, empty input, malformed dates and
the configured row limit fail before RouterOS connection. Errors identify CSV
lines.

Every router alias requires an `address_list` name. Names must be 1-64 characters,
start with an alphanumeric character, and contain only alphanumerics, `_`, `-`, or
`.`. There is deliberately no default: changing or omitting the configured list
invalidates pending plans before RouterOS is contacted.

## CLI

```bash
mikrotik-suspender plan --router lab --date 2026-07-17 --json
mikrotik-suspender apply --router lab --date 2026-07-17
```

`apply` creates a fresh plan, displays its hash and asks for confirmation before
applying that exact object. `--yes` is intended for already-controlled automation.
Exit codes: `0` success, `1` validation/transport failure, `2` CLI syntax, `3`
plan conflict, `4` cancelled, `5` partial apply failure. JSON mode writes valid
JSON to stdout.

## HTTP and web

Protected endpoints are `POST /validate`, `POST /plan`, `POST /apply` and the
legacy options endpoints. `/apply` accepts `{router, plan_id, confirmed}` and only
uses plans held in this process. Restarting the process expires pending plans.
`/health/live` proves the process responds; `/health/ready` checks initialized
local data. Neither probe contacts RouterOS.

The browser UI uses the same plan/apply flow. Its bearer token exists only in
JavaScript memory and is never written to local/session storage or static assets.

## Docker

```bash
docker compose build
docker compose up -d
curl http://127.0.0.1:8000/health/ready
```

Compose publishes only on host loopback and the image runs as a non-root user. The
container binds `0.0.0.0` internally, so both the image and Compose fail startup
without `API_KEY`; host-loopback publication is defense in depth, not an auth bypass.
If you intentionally publish externally, also terminate TLS at a trusted reverse
proxy. Secrets remain environment/runtime concerns, never image build args.

## Recovery and reconciliation

There is no blind rollback because removing an address may conflict with another
operator's intent. On partial failure, preserve the result report, correct the
cause, generate a fresh plan and apply it. To reverse a suspension, review and
change the address-list entry directly under your RouterOS change procedure, then
re-plan. A stale plan is evidence that state changed, not an error to bypass.

A RouterOS timeout is an uncertain outcome: the synchronous library call may still
be alive in a worker thread. The process quarantines that client, skips disconnect,
and blocks further operations on it. Do not retry blindly; let the outstanding call
settle, inspect RouterOS state independently, then restart the process and reconcile
with a fresh plan. This project does not claim cancellation the library cannot do.

The browser apply-result formatter is intentionally small. This repository has no
JavaScript test harness yet; Python contract tests pin the response counters and the
UI's partial-failure branch until a browser-level harness is introduced.

## Opt-in CHR laboratory

Create an isolated CHR instance, configure a CA-signed `api-ssl` certificate, a
  restricted test user, and a disposable firewall rule consuming the exact list
  configured as the alias's `address_list` (for example, `lab-suspensions`). Point
  a test alias at it and use documentation-only IP ranges. No automated test in
  this repository connects to CHR or any real router.

## Development

```bash
ruff check .
mypy core use_cases adapters api cli
pytest -q
python -m build
pip-audit
docker build -t mikrotik-suspender:local .
```

See `SECURITY.md`, `CONTRIBUTING.md` and `CHANGELOG.md`.
