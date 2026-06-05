# Technical Debt

Known limitations and post-publish improvements for the
`mikrotik-suspender` tool. These items are intentional gaps from
the initial opensource release — fixing them in a follow-up
release (or accepting community PRs) will harden the tool
significantly.

## High priority — security

### ~~Authentication on all endpoints~~ (closed in v0.2.0)

**Status**: ✅ Implemented — `Authorization: Bearer <API_KEY>`
gates all sensitive endpoints. The key is read from the `API_KEY`
env var; when unset, the dependency is a no-op (dev mode) and a
loud WARNING is logged at startup. `/health` and `/` (static
frontend) remain public.

- Implementation: `api/auth.py` with `verify_api_key` FastAPI
  dependency; uses `secrets.compare_digest()` for timing-safe
  comparison.
- Optional, not required: keeps dev frictionless. Owners who
  expose the service to a non-loopback network **must** set
  `API_KEY` (see README, "Authentication" section).

For higher security needs (mTLS, reverse proxy auth), the same
threat model applies — see the previous risk list below for
context, and the Authentication section in the README for setup.

### IP address validation

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

### Tag v0.2.0

The first public release (v0.1.0) was tagged at the initial commit.
Since then the repo has accumulated 4 new features (CSV cleanup,
optional Bearer auth, Docker support, CLI). Tag a new release:

```bash
git tag -a v0.2.0 -m "Bearer auth, Docker support, CLI for technicians"
git push origin v0.2.0
```

### CI pipeline (GitHub Actions)

Add a workflow (`.github/workflows/ci.yml`) that runs on PRs and
`main`:

- `python -m venv .venv && pip install -r requirements.txt`
- `pytest tests/ -v`
- `pip-audit -r requirements.txt` (catches new CVEs in deps)
- Optional: `ruff check` or `flake8` for linting (not currently
  configured).
- Optional: `docker build` smoke test (catches Dockerfile breakage).

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
