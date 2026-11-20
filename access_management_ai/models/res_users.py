# Copyright (C) NexGen Solutions
from datetime import timedelta

from odoo import SUPERUSER_ID, Command, _, api, fields, models
from odoo.exceptions import AccessDenied, UserError
from odoo.http import request

from .access_role import _user_group_field

ACCESS_FIELDS = ('access_read_only', 'access_prevent_login', 'access_disable_dev_mode',
                 'access_block_external_api')


class ResUsers(models.Model):
    _inherit = 'res.users'

    access_read_only = fields.Boolean(
        string='View Only',
        help="The user can browse data but cannot create, edit, delete or "
             "export business records.")
    access_prevent_login = fields.Boolean(
        string='Prevent Login',
        help="Block this user from logging in (existing sessions are unaffected).")
    access_disable_dev_mode = fields.Boolean(
        string='Disable Developer Mode',
        help="Force the developer/debug mode off for this user.")
    access_block_external_api = fields.Boolean(
        string='Block External API',
        help="Block this user from authenticating through XML-RPC/JSON-RPC and "
             "external API calls (interactive web login still works).")
    password_write_date = fields.Datetime(string='Password Last Changed', readonly=True)
    password_expiry_date = fields.Datetime(
        string='Password Expires On', compute='_compute_password_expiry_date')

    role_line_ids = fields.One2many(
        'access.role.line', 'user_id', string='Roles',
        help="Security roles granted to this user. Each role adds its groups; "
             "an optional date window limits when it applies.")
    access_role_managed_group_ids = fields.Many2many(
        'res.groups', 'access_role_managed_group_rel', 'user_id', 'group_id',
        string='Groups Added by Roles', copy=False, groups='base.group_system',
        help='Tracks groups actually added by roles, so revocation preserves previously assigned groups.')
    access_rule_ids = fields.Many2many(
        'access.management',
        'access_management_user_rel', 'user_id', 'rule_id',
        string='Access Rules',
        help="Access Rules that directly target this user.")
    access_custom_group_ids = fields.Many2many(
        'access.management.group',
        'access_management_group_res_users_rel',
        'res_users_id', 'access_management_group_id',
        string='Access Groups',
        help="Custom Access Groups this user belongs to.")
    applied_rule_ids = fields.Many2many(
        'access.management',
        compute='_compute_applied_rule_ids',
        string='Effective Access Rules',
        help="All active Access Rules currently applying to this user "
             "(via direct assignment, Odoo groups, or Access Groups), "
             "respecting each rule's schedule.")
    access_rule_count = fields.Integer(compute='_compute_access_counts')
    access_group_count = fields.Integer(compute='_compute_access_counts')
    access_role_count = fields.Integer(compute='_compute_access_counts')

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + list(ACCESS_FIELDS) + ['password_expiry_date']

    def _compute_applied_rule_ids(self):
        AM = self.env['access.management']
        for user in self:
            if not user.id:
                user.applied_rule_ids = AM.browse()
                continue
            user.applied_rule_ids = AM._rules_for_user(user.id)

    def _compute_access_counts(self):
        for user in self:
            user.access_rule_count = len(user.access_rule_ids)
            user.access_group_count = len(user.access_custom_group_ids)
            user.access_role_count = len(user.role_line_ids)

    # ------------------------------------------------------------------
    # Password expiry
    # ------------------------------------------------------------------
    def _password_expiry_days(self):
        """ Effective expiry (smallest positive among the user's profiles), 0 = never. """
        self.ensure_one()
        rules = self.env['access.management']._rules_for_user(self.id)
        days = [r.password_expiry_days for r in rules if r.password_expiry_days > 0]
        return min(days) if days else 0

    def _compute_password_expiry_date(self):
        for user in self:
            days = user._password_expiry_days()
            base = user.password_write_date or user.create_date
            user.password_expiry_date = base + timedelta(days=days) if (days and base) else False

    # ------------------------------------------------------------------
    # Security roles -> group synchronization
    # ------------------------------------------------------------------
    def _access_roles_sync_groups(self):
        """ Make each user's directly-assigned groups reflect their (enabled)
        role lines: enabled roles add their groups, disabled/removed roles take
        only *their* groups back, leaving the user's other groups untouched.

        The stored managed set contains only groups added by this mechanism.
        Groups the user already held before a role grant remain independent. """
        if not self:
            return
        gfield = _user_group_field(self.env)
        for user in self:
            enabled = set()
            managed = set(user.sudo().access_role_managed_group_ids.ids)
            # active_test=False so groups of archived roles are still reconciled
            # (the role's own ``active`` flag drives enable/disable via _enabled).
            for line in user.with_context(active_test=False).role_line_ids:
                groups = set(line.role_id._get_all_group_ids().ids)
                if line._enabled():
                    enabled |= groups
            current = set(user.sudo()[gfield].ids)
            to_add = enabled - current
            to_remove = (managed - enabled) & current
            next_managed = (managed & enabled) | to_add
            cmds = [Command.link(g) for g in to_add]
            cmds += [Command.unlink(g) for g in to_remove]
            values = {}
            if cmds:
                values[gfield] = cmds
            if next_managed != managed:
                values['access_role_managed_group_ids'] = [Command.set(sorted(next_managed))]
            if values:
                user.sudo().write(values)

    @api.model
    def _cron_sync_access_roles(self):
        """ Re-apply role-based groups so date-limited roles take effect/expire. """
        lines = self.env['access.role.line'].sudo().search([])
        lines.user_id._access_roles_sync_groups()

    # ------------------------------------------------------------------
    # Authentication hooks
    # ------------------------------------------------------------------
    def _check_credentials(self, credential, env):
        auth_info = super()._check_credentials(credential, env)
        user = self.sudo()
        is_superuser = user._is_superuser()
        interactive = env.get('interactive', True)

        if user.access_prevent_login and not is_superuser:
            raise AccessDenied(_("Access Denied: Your account login has been prevented by an administrator."))

        # Profile-level login prevention
        if not is_superuser:
            rules = self.env['access.management']._rules_for_user(user.id)
            if any(r.global_prevent_login for r in rules):
                raise AccessDenied(_("Access Denied: Your account login has been prevented by an administrator."))

        # External API (non-interactive RPC) block
        if not is_superuser and user.access_block_external_api and not interactive:
            raise AccessDenied(_("Access Denied: Your account login has been prevented by an administrator."))

        # Password expiry (only on interactive login)
        if not is_superuser and interactive:
            expiry = user.password_expiry_date
            if expiry and fields.Datetime.now() > expiry:
                raise AccessDenied(_("Access Denied: Your password has expired. Please reset your password."))
        return auth_info

    def _login(self, credential, user_agent_env):
        try:
            auth_info = super()._login(credential, user_agent_env)
        except AccessDenied:
            self.env['access.login.log']._track(
                'failed', login=credential.get('login'), request=request)
            raise
        user = self.sudo().browse(auth_info['uid'])
        self.env['access.login.log']._track('login', user=user, request=request)
        return auth_info

    # ------------------------------------------------------------------
    # Password change tracking
    # ------------------------------------------------------------------
    def _stamp_password_date(self, vals):
        if any(k in vals for k in ('password', 'new_password')):
            vals = dict(vals)
            vals['password_write_date'] = fields.Datetime.now()
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [self._stamp_password_date(v) for v in vals_list]
        users = super().create(vals_list)
        if any(f in vals for vals in vals_list for f in ACCESS_FIELDS):
            self.env.transaction.invalidate_ormcache()
            self.env.transaction.invalidate_access_cache()
        return users

    def write(self, vals):
        vals = self._stamp_password_date(vals)
        res = super().write(vals)
        if any(f in vals for f in (*ACCESS_FIELDS, 'access_rule_ids', 'access_custom_group_ids', 'group_ids', 'company_ids', 'company_id', 'active')):
            self.env.transaction.invalidate_ormcache()
            self.env.transaction.invalidate_access_cache()
        return res

    # ------------------------------------------------------------------
    # Navbar Switch User
    # ------------------------------------------------------------------
    @api.model
    def am_search_switchable_users(self, search='', limit=20):
        """ Users an Access Administrator can switch into from the navbar. """
        if not self.env.user.has_group('access_management_ai.group_access_manager'):
            return []
        domain = [
            ('share', '=', False),
            ('active', '=', True),
            ('id', '!=', self.env.uid),
            ('id', '!=', SUPERUSER_ID),
        ]
        search = (search or '').strip()
        if search:
            domain += ['|', ('name', 'ilike', search), ('login', 'ilike', search)]
        return self.sudo().search_read(
            domain, ['id', 'name', 'login'], limit=limit or 20, order='name, id')

    # ------------------------------------------------------------------
    # Admin actions: Login-as / Terminate sessions
    # ------------------------------------------------------------------
    def action_access_login_as(self):
        self.ensure_one()
        if not self.env.user.has_group('access_management_ai.group_access_manager'):
            raise UserError(_("Only Access Management administrators can use Login as."))
        if self._is_superuser():
            raise UserError(_("You cannot log in as the superuser."))
        return {
            'type': 'ir.actions.client',
            'tag': 'access_management_switch_user',
            'params': {'user_id': self.id, 'user_name': self.name},
        }

    def action_access_terminate_sessions(self):
        if not self.env.user.has_group('access_management_ai.group_access_manager'):
            raise UserError(_("Only Access Management administrators can terminate sessions."))
        for user in self:
            user._action_revoke_all_devices()
        return True

    def action_view_access_rules(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Access Rules'),
            'res_model': 'access.management',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.access_rule_ids.ids)],
            'context': {'default_user_ids': [Command.link(self.id)]},
        }

    def action_view_access_groups(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Access Groups'),
            'res_model': 'access.management.group',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.access_custom_group_ids.ids)],
            'context': {'default_user_ids': [Command.link(self.id)]},
        }

    def action_view_access_roles(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Security Roles'),
            'res_model': 'access.role',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.role_line_ids.role_id.ids)],
        }

    # ------------------------------------------------------------------
    # Cron: password expiry reminders
    # ------------------------------------------------------------------
    @api.model
    def _cron_password_expiry_reminders(self):
        now = fields.Datetime.now()
        users = self.search([('active', '=', True), ('share', '=', False), ('email', '!=', False)])
        for user in users:
            expiry = user.password_expiry_date
            if not expiry:
                continue
            if (expiry.date() - now.date()).days in (7, 1):
                template = self.env.ref(
                    'access_management_ai.mail_template_password_expiry_reminder',
                    raise_if_not_found=False)
                if template:
                    template.sudo().send_mail(
                        user.id, force_send=False, raise_exception=False)

    # ------------------------------------------------------------------
    # Client payload
    # ------------------------------------------------------------------
    @api.model
    def get_access_restrictions(self):
        """ Compact per-user restriction payload consumed by the web client. """
        rules = self.env['access.management']._rules_for_user(self.env.uid)
        read_only = self.env.user.access_read_only or any(r.readonly for r in rules)

        # Global chatter = profile-level flags (fallback for all models)
        chatter_global = {
            'hide': any(r.hide_chatter for r in rules) or any(r.global_hide_chatter for r in rules),
            'send_message': any(r.hide_send_message for r in rules)
                            or any(r.global_hide_send_message for r in rules),
            'log_note': any(r.hide_log_note for r in rules)
                        or any(r.global_hide_log_note for r in rules),
            'activities': any(r.hide_activities for r in rules)
                          or any(r.global_hide_activities for r in rules),
            'followers': any(r.hide_followers for r in rules) or any(r.global_hide_followers for r in rules),
            'attachments': any(r.global_hide_attachments for r in rules),
            'search': any(r.global_hide_chatter_search for r in rules),
        }
        global_cfg = {
            'hide_import': read_only or any(r.global_hide_import for r in rules),
            'hide_archive': read_only,
            'hide_print': any(r.global_hide_print for r in rules),
            'hide_action': any(r.global_hide_action for r in rules),
            'hide_export': read_only or any(r.global_hide_export for r in rules),
            'hide_spreadsheet': read_only or any(r.global_hide_spreadsheet for r in rules),
            'hide_filters': any(r.global_hide_filters for r in rules),
            'hide_groupby': any(r.global_hide_groupby for r in rules),
            'hide_custom_filter': any(r.global_hide_custom_filter for r in rules),
            'hide_custom_group': any(r.global_hide_custom_group for r in rules),
            'hide_favorites': any(r.global_hide_favorites for r in rules),
            'hide_searchbar': any(r.global_hide_searchbar for r in rules),
            'hide_search_panel': any(r.global_hide_search_panel for r in rules),
            'hide_add_property': read_only or any(r.global_hide_add_property for r in rules),
            'hide_delete': read_only or any(r.global_hide_delete for r in rules),
            'hide_filter_delete': any(r.global_hide_filter_delete for r in rules),
        }
        systray = set()
        for r in rules:
            if r.hide_systray_keys:
                systray.update(k.strip() for k in r.hide_systray_keys.split(',') if k.strip())

        models_cfg = {}
        for line in rules.model_access_ids:
            cfg = models_cfg.setdefault(line.model_name, {
                'hide_archive': False, 'hide_import': False, 'hide_spreadsheet': False,
                'hide_searchbar': False, 'hide_filters': False, 'hide_groupby': False,
                'hide_custom_filter': False, 'hide_custom_group': False,
                'hide_favorites': False, 'hide_search_panel': False, 'hide_add_property': False,
                'hide_export': False, 'hide_action': False,
                'hidden_filters': [], 'hidden_groupbys': [],
                'warn_mode': False, 'warn_message': '',
                'chatter': {'hide': False, 'send_message': False, 'log_note': False,
                            'activities': False, 'followers': False, 'attachments': False,
                            'search': False},
            })
            cfg['hide_archive'] |= not line.allow_archive or (not line.perm_write and not line.warn_mode)
            cfg['hide_import'] |= line.hide_import_button
            cfg['hide_spreadsheet'] |= line.hide_spreadsheet_button
            cfg['hide_searchbar'] |= line.hide_searchbar
            cfg['hide_filters'] |= line.hide_filters
            cfg['hide_groupby'] |= line.hide_groupby
            cfg['hide_custom_filter'] |= line.hide_custom_filter
            cfg['hide_custom_group'] |= line.hide_custom_group
            cfg['hide_favorites'] |= line.hide_favorites
            cfg['hide_search_panel'] |= line.hide_search_panel
            cfg['hide_add_property'] |= line.hide_add_property
            cfg['hide_export'] |= not line.allow_export
            cfg['hide_action'] |= line.hide_action
            ModelLine = self.env['access.management.model']
            for key in ModelLine._split_search_item_keys(line.hidden_filter_items):
                if key not in cfg['hidden_filters']:
                    cfg['hidden_filters'].append(key)
            for key in ModelLine._split_search_item_keys(line.hidden_groupby_items):
                if key not in cfg['hidden_groupbys']:
                    cfg['hidden_groupbys'].append(key)
            if line.warn_mode:
                cfg['warn_mode'] = True
                if line.warn_message and not cfg['warn_message']:
                    cfg['warn_message'] = line.warn_message
            ch = cfg['chatter']
            ch['hide'] |= line.chatter_hide
            ch['send_message'] |= line.chatter_hide_send_message
            ch['log_note'] |= line.chatter_hide_log_note
            ch['activities'] |= line.chatter_hide_activities
            ch['followers'] |= line.chatter_hide_followers
            ch['attachments'] |= line.chatter_hide_attachments
            ch['search'] |= line.chatter_hide_search
        return {
            'read_only': read_only,
            'disable_dev_mode': self.env.user.access_disable_dev_mode
                                or any(r.restrict_developer_mode for r in rules),
            'prevent_login': self.env.user.access_prevent_login
                             or any(r.global_prevent_login for r in rules),
            'chatter_global': chatter_global,
            'systray': sorted(systray),
            'global': global_cfg,
            'models': models_cfg,
        }


class ResUsersApiKeys(models.Model):
    _inherit = 'res.users.apikeys'

    def _check_credentials(self, *, scope, key):
        uid = super()._check_credentials(scope=scope, key=key)
        # Odoo 20 JSON-2 bearer authentication checks API keys directly,
        # without passing through res.users._check_credentials.
        if uid and scope == 'rpc' and uid != SUPERUSER_ID:
            user = self.env['res.users'].sudo().browse(uid)
            if user.access_block_external_api:
                return False
        return uid
