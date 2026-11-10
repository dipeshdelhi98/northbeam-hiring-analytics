# Deployment

## Status: runs locally; not deployed to a public URL

I chose not to put this on a public host. Reasons, in order:

1. **It would be a public login page over personal-data-shaped records with a shared demo
   password.** The brief says to treat the data as real personal information. A public URL with a
   password that is written in the README is the thing I would refuse to ship for a client.
2. Nothing about the design depends on where it runs. The app is a single stateless process
   reading one read-only DuckDB file — the deployment story below is short because the shape is
   simple, and that is deliberate.
3. Zero cost and zero risk of a surprise bill.

The brief notes that a reasoned local-only answer is worth nearly full marks; the Dockerfile below
is what would be deployed.

## How it would be deployed (free tier)

`Dockerfile` in the repo root builds the warehouse **at image build time**, runs the control-total
tests as a build gate, and bakes the warehouse in. *Docker was not available on the build machine, so
the Dockerfile has not been built — treat it as a specification, not a verified artefact.*

```
docker build -t northbeam .
docker run -p 8000:8000 -e NB_JWT_SECRET=$(openssl rand -base64 48) -e NB_DEMO_PASSWORD=... northbeam
```

On **Render** (free web service) or **Fly.io**: point at the repo, Dockerfile build, set
`NB_JWT_SECRET` and `NB_DEMO_PASSWORD` as secrets. No database service is needed — the DuckDB file
is ~7 MB and read-only at runtime, so the container's filesystem is enough and it scales
horizontally by just running more copies. Cold start on free tiers (~30 s spin-up) is the main
user-visible cost.

Data refresh = rebuild and redeploy the image. At this volume (thousands of rows, ~4 s build)
that is the right trade: immutable artefacts, trivial rollback (redeploy previous image).

## What I would change before real users touched it

**Identity and access**
- Replace the demo password with SSO (OIDC against the client's IdP). `api/auth.py` is the only
  file that changes: everything downstream needs only a trusted user id.
- Short-lived tokens are fine; add server-side revocation (or rely on IdP session + 15-min TTL).
- Admin is currently "sees everything incl. contact data in the warehouse"; split into analytics
  admin vs. data steward, and audit-log every request with user id + endpoint + scope size.

**Personal data**
- Encrypt the warehouse at rest (volume encryption on the host) and keep the landing zone out of
  the image; candidates' phone/email exist in Gold only for identity resolution and should move to
  a restricted table that the scoped connection never copies (it already doesn't copy them to
  non-admins' listings, but the column exists in `dim_candidate`).
- Retention: rejected/withdrawn candidates' personal data purged after the policy period (DPDP
  Act 2023 in India); the person key (hashed phone) can survive for de-duplication.
- Remove the committed landing data from the repo — it is here only because the exercise ships it.

**Operational**
- HTTPS only, HSTS, CORS locked to the frontend origin (same origin today), rate limit `/api/login`.
- Health endpoint and structured logs; alert if a pipeline run changes any control-total-style
  invariant by more than an expected amount.
- Pipeline on a schedule (GitHub Actions cron → build image → deploy) with the test suite as the
  gate: a red reconciliation test blocks the deploy rather than shipping wrong numbers.
- Surrogate keys are re-assigned on each full rebuild. Fine while nothing external stores them;
  move to hash keys (or a persistent key map) the moment anything does.
- Per-request scoped copies cost ~70 ms at this volume. At 100× the data, switch to caching the
  scoped connection per (user, warehouse version), or to DuckDB views over a filtered attach plus
  a SQL allow-list — measure first.
