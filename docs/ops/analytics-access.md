# GSC + GA4 access via service account

QuillCV uses a single service account to read Google Search Console and Google
Analytics 4 data from Claude (and any other tooling).

- **Service account**: `quillcv-analytics-reader@quillcv.iam.gserviceaccount.com`
- **GCP project**: `quillcv`
- **Credentials file**: `~/.config/quillcv/g4-sa.json` (do not commit)

The Search Console API and Google Analytics Admin/Data APIs are already enabled
in the `quillcv` GCP project.

## How it's wired

`.mcp.json` at the repo root registers two project-scoped MCP servers that both
read the same credentials file:

| Server | Package | Purpose |
| --- | --- | --- |
| `ga4` | [`analytics-mcp`](https://github.com/googleanalytics/google-analytics-mcp) (official, Google) | GA4 admin + data reports |
| `gsc` | [`mcp-server-gsc`](https://github.com/ahonn/mcp-server-gsc) | Search Console search analytics |

Claude Code launches each on demand via `uvx` / `npx`, so there is nothing to
install manually beyond `uv` and `node`.

## Granting the SA access (one-time per property)

The SA's credentials are valid, but having credentials does not grant access —
it only proves *who* is calling. You must add the SA email to each property:

### Search Console

1. Open <https://search.google.com/search-console>
2. Select the `quillcv.com` property
3. **Settings → Users and permissions → Add user**
4. Email: `quillcv-analytics-reader@quillcv.iam.gserviceaccount.com`
5. Permission: **Restricted** (read-only) is sufficient

### Google Analytics 4

1. Open <https://analytics.google.com> → admin (cog) → property **QuillCV**
2. **Property access management → +** (top right) **→ Add users**
3. Email: `quillcv-analytics-reader@quillcv.iam.gserviceaccount.com`
4. Role: **Viewer** (read-only) is sufficient

## Verifying access

After granting, run:

```bash
uv run --no-project --with google-auth --with requests python - <<'PY'
from google.oauth2 import service_account
import google.auth.transport.requests as greq, requests
SA = "/home/daniel/.config/quillcv/g4-sa.json"
SCOPES = [
    "https://www.googleapis.com/auth/webmasters.readonly",
    "https://www.googleapis.com/auth/analytics.readonly",
]
c = service_account.Credentials.from_service_account_file(SA, scopes=SCOPES)
c.refresh(greq.Request())
H = {"Authorization": f"Bearer {c.token}"}
print("GSC:", requests.get("https://www.googleapis.com/webmasters/v3/sites", headers=H).text[:300])
print("GA4:", requests.get("https://analyticsadmin.googleapis.com/v1beta/accountSummaries", headers=H).text[:600])
PY
```

A successful grant returns the property/site list instead of `{}`.

## Notes

- The credentials file path uses `${HOME}` in `.mcp.json` so the config is
  portable across machines, but the file itself must exist locally — it is
  never committed.
- Only the read-only scopes are requested
  (`webmasters.readonly`, `analytics.readonly`); the SA cannot modify settings,
  goals, or property data even if access were misgranted.
- After updating `.mcp.json` you must approve the new project-scoped servers
  in Claude Code (`/mcp` or restart). Claude prompts on first use of a new
  project's MCP config.
