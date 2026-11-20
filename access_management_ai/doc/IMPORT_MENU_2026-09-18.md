# Contacts Import menu — 20.0.1.0.10

On the live Odoo 20 Enterprise build, Contacts had no Actions button despite
`base_import` being installed, create access being allowed, and import restrictions
being disabled. Several Enterprise cog-menu predicates still read `env.isSmall`,
which Odoo 20's UI plugin migration replaces with `env.services.ui.isSmall`.
The old accessor throws. The cog menu stores that failure internally and renders
no items, hiding Import and the Actions button without a visible error dialog.

The addon now supplies the compatibility accessor only to cog-menu visibility
predicates. It handles items already registered and items registered later.
Native predicates and permission checks remain intact; core/Enterprise source
files are unchanged. No breadcrumb template replacement was needed.

Browser validation covers Import in list and kanban views, opening the upload
screen, Global Hide Import, per-model Hide Import Button, Global Read-Only,
denied create permission, and restoring Import after removing restrictions.
Test fixtures run on the isolated Enterprise database copy. No contact data is
uploaded or imported during these checks.

Evidence, source snapshot and database/filestore backups are in
`/tmp/am20-contact-import/`. After applying the fix, refresh Contacts, leave all
rows unselected, then use the three-dot Actions button beside Contacts → Import.

Deployed to `v20_ent` as `20.0.1.0.10`. The upgrade completed without errors.
The live verification logs in directly as `demo`, opens the normal (non-debug)
Contacts list, finds Actions → Import, and opens the Upload screen successfully.
No browser errors occurred and no contact data was imported. The focused import
regression and the existing full browser suite both passed. Odoo is running on
port 2222; the temporary test server was stopped.
