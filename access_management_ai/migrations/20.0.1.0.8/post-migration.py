from odoo import Command, SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    module = env['ir.module.module'].search([('name', '=', 'access_management_ai')])
    # Older registrations can lack base_import_module's default, making the
    # installed application disappear under Odoo's default Apps filter.
    if 'module_type' in module._fields and not module.module_type:
        module.module_type = 'official'

    users = env['access.role.line'].with_context(active_test=False).search([]).user_id
    for user in users:
        # Legacy assignments do not retain grant provenance. Preserve their
        # existing role-managed semantics; new grants track only added groups.
        legacy_groups = user.with_context(active_test=False).role_line_ids.role_id._get_all_roles().group_ids
        managed = legacy_groups & user.group_ids
        user.access_role_managed_group_ids = [Command.set(managed.ids)]
    users._access_roles_sync_groups()

    # Retain legacy request revocation behavior while tracking ownership for
    # new approvals. Old versions did not record whether a grant predated them.
    profiles_seen = set()
    for request in env['access.request'].search([('state', '=', 'approved')], order='id'):
        if request.role_id:
            request.granted_role_line_id = env['access.role.line'].search([
                ('role_id', '=', request.role_id.id), ('user_id', '=', request.user_id.id),
            ], limit=1)
        key = (request.profile_id.id, request.user_id.id)
        if request.profile_id and key not in profiles_seen and request.user_id in request.profile_id.user_ids:
            request.profile_grant_owned = True
            profiles_seen.add(key)
