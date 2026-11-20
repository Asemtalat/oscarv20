# Odoo 20 functional migration

Module: `access_management_ai` — version `20.0.1.0.7`.

Verification target: the Odoo 20 source checkout supplied by the user, PostgreSQL
port 5433, and a snapshot of `v20_ent`. This report concerns the module, not a
replacement for Odoo's database-wide major-version upgrade service.

## Changes

- Unified `ir.access` ACLs and record restrictions; module-owned legacy security
  XML-ID conversion; regression checks for CRUD, record domains and fail-closed
  validation.
- Uncached time-dependent restrictions; cache invalidation for direct/reverse
  assignments and custom groups; scheduled and multi-company menu refresh.
- Parent-company restrictions on child configuration records and dashboard rows.
- Global read-only view/export behavior, soft restrictions and warn-mode behavior.
- Nested role changes and archiving now reconcile parent-role users' groups.
- Request creation/ownership controls and administrator-only approval, rejection
  and revocation. AI wizards require Access Administrator membership.
- Odoo 20 `BinaryBytes`/binary-content handling for both JSON transfer wizards.
- Odoo 20 typed configuration access (`get_str`, `get_bool`, `set_str`) for AI
  configuration, consent and model catalogues.
- OWL proxy state, signal references, `useProps`, `useOnChange`, explicit `this`
  template bindings, and stale-response protection in asynchronous selectors.
- Chatter/search/action/archive/export/property/spreadsheet presentation patches;
  saved-filter deletion protection; settings icon path.
- Startup synchronization uses the user service and preserves impersonation
  metadata. User switching uses POST JSON-RPC with session rotation.
- JSON-2 bearer API-key enforcement for Block External API.
- QWeb `t-out` migration so report values actually render, not merely the layout.

## Automated verification

`tests/check_static.py` checks Python/XML/JavaScript syntax, declared data files,
ACL operation values and known removed APIs. At verification time it covered
45 Python files, 33 XML files and 15 JavaScript files.

`tests/test_migration.py` contains 30 Odoo transaction tests covering:

- Native permission preservation and blocked create/write/unlink.
- All four record-domain operations, direct soft restrictions, warn mode.
- Scheduled restrictions, date/hierarchy filters, invalid-domain rejection.
- Custom/reverse group assignments and company switching.
- Global read-only, export suppression and excluded export fields.
- Fields/chatter/views, hidden actions and saved-filter deletion.
- Role grant/expiry/revocation, nested-role changes, bulk assignment.
- Request ownership and submission/approval/revocation, with email mocked.
- JSON import/export, missing-reference logs and report output values.
- Password expiry, login controls and API-key restrictions.
- AI-generated rule/role application, mocked provider transports, consent and
  provider model-list response shapes.
- Legacy module ACL/global-rule conversion using synthetic pre-20 tables,
  including a second idempotent execution.
- Every module-owned non-QWeb view.

The suite passed with **30 tests, 0 failures, 0 errors** on each of the
existing-data clone `am20_verify_20260917` and `am20_install_20260917`, which was
installed from an empty database. The latter also verifies repeat upgrades
after clean installation.

`tests/browser_verify.cjs` verifies login, all 15 custom JS modules, rule tabs,
selector editing/saving, list/kanban views, dashboards, wizard/settings forms,
three actual PDF downloads, restricted chatter/search/action controls and
switch-user/switch-back. It creates fixtures only in the isolated database.
The final full run passed with no browser console/page errors; all three
downloads had valid PDF headers (19,319, 19,045 and 34,946 bytes).

To run source checks from the module directory:

```bash
PYTHONPATH=/opt/odoo20/python-packages python3.12 tests/check_static.py
```

To run backend tests, use the supplied Odoo server command with a **test**
database and add:

```text
-u access_management_ai --test-enable --test-tags=/access_management_ai --stop-after-init --no-http
```

The browser script accepts `AM20_URL`, `AM20_DB`, `AM20_LOGIN`, `AM20_PASSWORD`,
`AM20_PUPPETEER`, and `AM20_ARTIFACTS`. `AM20_SMOKE_ONLY=1` performs login/asset
checks without creating fixtures. Do not run the full browser fixture suite
against a production database.

## Evidence and recovery

Temporary evidence directory: `/tmp/access-management-v20-meIDcw/`.

- `v20_ent_before.dump`: initial database snapshot.
- `v20_ent_pre_deploy.dump`: fresh pre-deployment snapshot, verified readable
  with `pg_restore -p 5433 --list` (PostgreSQL 17 archive format).
- `backend-tests.log`, `clean-install-tests.log`: test runs, including initial
  failures and subsequent passing runs. Use the final test summary.
- `browser-server.log`: isolated-server and PDF rendering logs.
- `live-upgrade.log`, `live-server.log`: deployment and restarted-server logs.
- `admin-home.png`, `element-selector.png`, `restricted-contact.png`: UI evidence.

The isolated databases and evidence are retained for review; they contain test
fixtures and must not be used as production databases. Copy the snapshots to
durable backup storage before `/tmp` is cleaned. Restore to a new database first
when inspecting a backup; do not overwrite `v20_ent` blindly.

## Scope and remaining environment checks

- Live AI provider calls were not made. Provider transport/response handling and
  wizard application were tested with mocks. Validate the configured account,
  API key, selected model and any Cursor CLI/proxy separately before enabling
  live AI generation. No assurance is made about external model availability.
- Outbound email delivery was not tested against a real mail server.
- The wider installation logs missing optional `markdown2` and duplicate AI
  setting labels shared with `dynamic_dashboard_ai_nexgen`. These warnings did
  not prevent installation or the tested workflows; no unrelated add-on or
  global Python environment was changed to suppress them.
- The legacy conversion test covers this module's original ACLs and global
  record rules. A full, unconverted Odoo 19 database was not upgraded during
  this task; core/Enterprise schema upgrades remain Odoo's responsibility.
- UI hiding is not field-level data security. Use native permissions and hard
  record domains for confidentiality. Warn mode does not override native ACLs.
- Verification applies to the supplied Odoo 20 checkout. Re-run the suite after
  updating that development branch or changing dependent modules.

## Deployment

On 2026-09-17, the live upgrade completed successfully (exit 0), and `v20_ent`
reports `access_management_ai` installed at `20.0.1.0.7`. The server was restarted
with the supplied options on `http://localhost:2222` (PID 95488 at handoff).

Before and after deployment, the database had **8 access profiles, 0 roles and
0 requests**. Functional test fixtures were confined to the isolated databases;
the live check only authenticates and loads frontend assets.

The live browser smoke check passed: administrator login succeeded, all 15
custom JavaScript modules loaded, and there were no module-loader, console or
page errors. Its first cold-asset attempt exposed a test timing issue (form
hydration cleared credentials); the test now waits for the interactive login
form before typing, and the rerun completed with `SMOKE_OK`.
