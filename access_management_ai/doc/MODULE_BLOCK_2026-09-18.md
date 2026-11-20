# Module management restriction — 20.0.1.0.9

The live demo account has native Odoo system-administrator privileges. Rule 7
had `block_module_management=True` and `readonly=False`, so this option must work
independently of Global Read-Only.

The original guard covered the standard module operations and record writes,
but Apps still rendered Activate/Upgrade/Uninstall controls. The uninstall dialog,
industry download and Apps-list update had no early profile check. The ZIP import
path elevated privileges before importing data, bypassing the record-write guard.

The update removes module-changing buttons from kanban/list/form views, hides
Update Apps List and Import Module menus, and makes module toggles read-only in
Settings. It rejects direct module operations, uninstall-dialog requests,
industry downloads, module ZIP imports and Settings requests that change modules.
Ordinary settings and browsing Apps remain available. Removing the restriction
restores the controls after refresh.

`base_import_module` is now an explicit dependency so its import implementation
always loads before the security override. It was already installed in the live
database.

Validation: 62 backend regressions pass with zero failures/errors on both the
Enterprise database copy and the clean test database. The focused browser test
checks all three Apps views, ten module-operation RPC entry points, unchanged
module state and restoration after disabling the restriction.

Evidence and pre-update backups: `/tmp/am20-module-block/`. The source snapshot,
database dump and filestore archive were saved before deployment. Browser tests
that exercise module-operation RPCs use an isolated database; live checks only
read views, request the uninstall dialog and attempt a no-op metadata write.

Live result: `v20_ent` upgraded to `20.0.1.0.9` without errors. Direct login as
`demo` confirms the module-changing controls are absent in kanban/form/list,
and both safe RPC checks raise `AccessError`. No browser errors occurred.
Global Read-Only remains off, Block Module Management remains on for rule 7,
and the saved profile settings and demo group assignments match the pre-update
snapshot. Odoo is running on port 2222; the temporary test server was stopped.
