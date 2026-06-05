# Technical Debt

Known limitations and post-publish improvements for the
`mikrotik-suspender` tool. These items are intentional gaps from
the initial opensource release — fixing them in a follow-up
release (or accepting community PRs) will harden the tool
significantly.

## High priority — security

### Authentication on all endpoints

**Status**: None of the 5 endpoints (`/preview`, `/script`,
`/addOptions`, `/readOptions`, `/addDoc`) require authentication.

**Risk**: The default `HOST=127.0.0.1` mitigates this for local
deployments, but anyone with network access to the service can:

- Trigger MikroTik firewall changes (suspend / unsuspend IPs).
- Read and modify the SQLite options database.
- Read and modify the local CSV.

**Fix options** (in order of complexity):

1. API key in `Authorization: Bearer` header — simplest.
2. mTLS for service-to-service — strongest.
3. Front with an authenticating reverse proxy (Caddy, nginx,
   Traefik) — flexible, doesn't require code changes.

### IP address validation

**Status**: `api/schemas.py` declares `IP_MIKROTIK: str` with no
validation. Any string is accepted.

**Risk**: A malicious client could pass `127.0.0.1` to attempt
SSRF against internal services, or non-IP strings that crash the
routeros-api client deep in the stack.

**Fix**: Add a Pydantic `field_validator` on `IP_MIKROTIK` that:

- Rejects non-IP strings.
- Optionally rejects private/loopback ranges if the service is
  exposed externally.
- Optionally rejects public IPs if the service should only
  operate on internal routers.

### CORS hardening

**Status**: `main.py` sets `allow_credentials=True` with
`allow_origins` read from env vars. If the env is misconfigured
(e.g., wildcard or untrusted origin), browsers will send cookies
cross-origin and the CORS spec explicitly forbids this combination.

**Fix**:

- Validate the origin list at startup: reject `*` when
  `allow_credentials=True`.
- Document the security implication in `.env.example`.
- Add tests that check the middleware config at boot.

## Medium priority — operations

### CI pipeline (GitHub Actions)

Add a workflow (`.github/workflows/ci.yml`) that runs on PRs and
`main`:

- `python -m venv .venv && pip install -r requirements.txt`
- `pytest tests/ -v`
- `pip-audit -r requirements.txt` (catches new CVEs in deps)
- Optional: `ruff check` or `flake8` for linting (not currently
  configured).

### Tag v0.1.0

Mark the first public release with a git tag. The current HEAD
is the initial public commit.

```bash
git tag -a v0.1.0 -m "Initial opensource release"
git push origin v0.1.0
```

### Online demo deployment

For discoverability, deploy a sandboxed demo to a free tier:

- HuggingFace Spaces (free CPU).
- Railway.app.
- Fly.io.

The demo **must** be clearly marked as such, with no real
MikroTik or production credentials. Use the sample data and a
fake router endpoint that returns canned responses.

## Low priority — features

### Gitops CSV (URL-backed)

The operator currently edits `data/clientes.csv` directly. For
teams that prefer a gitops workflow, add a `URLSheetReader`
adapter that fetches the CSV from a configurable URL (e.g., a
raw GitHub URL). This keeps an audit trail of who changed which
IPs and when.

### Multi-adapter Sheets support

If users request Google Sheets integration, add a
`GoogleSheetsReader` adapter as an opt-in (selected via env
var) alongside the default `CSVSheetReader`. Use `extras_require`
in packaging so the Google dependencies are only installed when
needed:

```bash
pip install mikrotik-suspender[google-sheets]
```

### Prometheus metrics endpoint

Add `/metrics` returning request counts, latencies, and
suspension outcomes for ops monitoring.

### Migrate-from-Sheets script

A one-time CLI helper for users with existing Google Sheets
data:

```bash
python -m mikrotik_suspender migrate-from-sheets \
  --credentials service-account.json \
  --spreadsheet-id abc123 \
  --range Clientes!A1:B100 \
  --output data/clientes.csv
```

## Tracking

Each item should become a GitHub Issue for visibility and
community contribution. Link related issues in commit messages
with `#<issue-number>`.
