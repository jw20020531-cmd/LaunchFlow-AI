# LaunchFlow MVP operations

## Pilot setup

Set unique random database passwords before first initialization. Use a trusted TLS reverse proxy pointing to the loopback web port, set `APP_ORIGIN` to the exact public HTTPS website origin and set `SECURE_COOKIES=true`. Keep database and API ports private. Disable proxy logging of cookies, bodies and authorization headers. Test the link and owner login using the real pilot hostname before enrolling clients.

Use the CLI via `docker compose exec api python -m app.cli`:

| Command | Use |
|---|---|
| `provision --email ... --workspace ...` | Create one owner with an interactive password. |
| `reset-password --email ...` | Set a new password and invalidate owner sessions. |
| `delete-workspace --id ...` | Permanently remove one workspace after typed confirmation. Record its ID privately for restore reconciliation. |
| `revoke-all-access` | Invalidate all sessions and review links after a restore. Requires typed confirmation. |

## Backup and restore

Have the operator schedule a daily custom-format `pg_dump`, encrypt it with an operator-managed key and transfer it to access-controlled storage separate from the host. Keep at most 14 days of backups, monitor dump failures and keep a minimal protected record of workspace deletions. The command below writes a temporary dump to the DB container. Copy it using `docker compose cp`, encrypt it immediately, verify checksum of the encrypted copy and remove the temporary plaintext dump from both locations. Never write backups to the source tree.

```powershell
docker compose exec db pg_dump -U postgres -Fc -f /tmp/launchflow.dump launchflow
```

For a restore drill, start a separate isolated stack or database with the application role present. Use `pg_restore --exit-on-error` with an operator credential and check for successful completion. Reapply recorded deletions before reopening any restored data. Run `revoke-all-access`, check the Alembic version and relevant row counts, and perform a synthetic request → review → decision. Record the backup age and time to restore against the proposed 24-hour and 4-hour targets. Repeat after migration changes. The backup service is operator-managed.

## Privacy

Tell pilot agencies who operates and can access the installation, how long data is kept, and which provider receives what data if they enable AI. Owner exports are available in Settings. Give notice before deleting inactive pilot workspaces under the proposed 90-day policy. Keep AI disabled until vendor and workspace data-use terms are agreed. Revocable links are bearer credentials. Keep them in the intended client channel and rotate them after misdelivery.

## Verification and scope changes

The Windows development environment was used for PostgreSQL 18 backend tests and a browser smoke test against a built Next.js server and native PostgreSQL. Docker Compose and encrypted backup restoration require a separate verification before live use. The first migration uses database constraints for project/request scope and decisions, with revision pointer checks in the service. Cursors use primary-key order and date/time calculations use the configured workspace zone. No live LLM provider has been exercised.
