# LaunchFlow AI

LaunchFlow helps web agencies collect website copy, review an exact revision and record the client's decision. It includes a checklist, version history, revocable client links and a status note you can copy to your existing communication channel.

[Try the public interactive demo](https://jw20020531-cmd.github.io/LaunchFlow-AI/). Switch between agency and client views to try submission, revision, and approval on a sample request. The demo saves progress in your browser.

## Run locally with Docker Compose

Requires Docker with Compose v2. In PowerShell, from the repository root:

```powershell
Copy-Item .env.example .env
docker compose up -d --build
docker compose exec api python -m app.cli provision --email owner@example.test --workspace "Demo Agency"
```

Choose a password when prompted, then sign in at [http://localhost:3000](http://localhost:3000). Use the same hostname throughout. Compose publishes only the web port on loopback, and creates a separate non-superuser PostgreSQL role for the app. The example passwords are for local use. The database initialisation script runs once on a fresh volume.

1. Create a website project and add a copy request.
2. Create a client link and open it in a private window. Submit example copy.
3. Refresh the owner view, save an edited revision if needed and share the saved version.
4. Refresh the client view and approve or request changes. Check the agency's history and readiness indicator.
5. Draft a status note from the checklist, review it and copy it. Rotate or revoke the client link from the workspace when needed.

Manual drafting is available by default. To enable optional AI, configure `LLM_URL` (the full chat completions-compatible endpoint), `LLM_MODEL` and any required `LLM_API_KEY` in the server environment, recreate the API service and opt in under Settings. Each AI request needs a matching reviewed snapshot before the server contacts the provider. An unavailable provider leaves the manual route usable.

## Development checks

From `api/`, install `requirements.txt` in an isolated environment and run `python -m pytest -q`. The default test database is disposable SQLite. Set `LAUNCHFLOW_TEST_DATABASE_URL` to a fresh PostgreSQL database named with the prefix `launchflow_test_` to exercise real row locking. Tests apply migration 0001. Reuse neither production nor pilot databases.

From `web/`, run `npm ci`, `npm run typecheck` and `npm run build`. To run the browser flow against a local stack, provision a synthetic owner, install Playwright Chromium (`npx playwright install chromium`), set `LAUNCHFLOW_TEST_EMAIL` and `LAUNCHFLOW_TEST_PASSWORD` for that owner, and run `npx playwright test`. Set `PLAYWRIGHT_CHANNEL=msedge` to use installed Edge instead.

See [operations](docs/operations.md) before using real client data and the [pilot runbook](docs/pilot-runbook.md) to evaluate the workflow.

