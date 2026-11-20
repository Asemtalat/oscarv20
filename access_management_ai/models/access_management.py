# Copyright (C) NexGen Solutions
import pytz

from odoo import api, fields, models, tools


def _tz_selection(self):
    return [(tz, tz) for tz in sorted(pytz.all_timezones, key=str.lower)]


class AccessManagement(models.Model):
    _name = 'access.management'
    _description = 'Access Management Rule'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc, id desc'

    name = fields.Char(required=True, tracking=True, translate=True)
    active = fields.Boolean(default=True, tracking=True)
    tag_ids = fields.Many2many('access.management.tag', string='Tags')
    sequence = fields.Integer(default=10)
    company_ids = fields.Many2many(
        'res.company', 'access_management_company_rel', 'rule_id', 'company_id',
        string='Companies',
        help="Limit this rule to these companies. Leave empty to apply in every company.")
    audit_reason = fields.Char(string='Reason for Change', store=False)

    user_ids = fields.Many2many(
        'res.users', 'access_management_user_rel', 'rule_id', 'user_id',
        string='Users', domain=[('share', '=', False)],
        help="Users this rule applies to.")
    group_ids = fields.Many2many(
        'res.groups', 'access_management_group_rel', 'rule_id', 'group_id',
        string='Groups',
        help="Every user member of these groups is subject to this rule.")
    custom_group_ids = fields.Many2many(
        'access.management.group', 'access_management_custom_group_rel',
        'rule_id', 'group_id',
        string='Access Groups',
        help="Custom access groups this rule applies to.")

    # Menus / apps to hide
    menu_ids = fields.Many2many(
        'ir.ui.menu', 'access_management_menu_rel', 'rule_id', 'menu_id',
        string='Hidden Menus',
        help="These menus (and their sub-menus) are hidden from the targeted users.")

    # Reports / actions to remove from the contextual (cog) menu
    report_ids = fields.Many2many(
        'ir.actions.report', 'access_management_report_rel', 'rule_id', 'report_id',
        string='Hidden Reports',
        help='Hide specific reports (Print menu) from targeted users.')
    action_ids = fields.Many2many(
        'ir.actions.act_window', 'access_management_action_rel', 'rule_id', 'action_id',
        string='Hidden Actions',
        help='Hide specific window actions (Action menu) from targeted users.')
    server_action_ids = fields.Many2many(
        'ir.actions.server', 'access_management_server_action_rel', 'rule_id', 'action_id',
        string='Hidden Server Actions',
        help='Hide specific server actions from targeted users.')
    client_action_ids = fields.Many2many(
        'ir.actions.client', 'access_management_client_action_rel', 'rule_id', 'action_id',
        string='Hidden Client Actions',
        help='Hide specific client actions from targeted users.')
    url_action_ids = fields.Many2many(
        'ir.actions.act_url', 'access_management_url_action_rel', 'rule_id', 'action_id',
        string='Hidden URL Actions',
        help='Hide specific URL actions from targeted users.')

    # Chatter
    hide_chatter = fields.Boolean(string='Hide Chatter', help='Completely hide the chatter area (bottom/right side) on all models for these users.')
    hide_send_message = fields.Boolean(string='Hide Send Message', help='Hide the Send Message button in the chatter on all models.')
    hide_log_note = fields.Boolean(string='Hide Log Note', help='Hide the Log Note button in the chatter on all models.')
    hide_activities = fields.Boolean(string='Hide Activities', help='Hide the Schedule Activity button in the chatter on all models.')

    readonly = fields.Boolean('Global Read-Only', help='Make the entire system read-only for these users. They will not be able to create, edit, or delete anything.')
    hide_followers = fields.Boolean(string='Hide Followers', help='Hide the followers section (the user icons and Add Followers button) in the chatter.')
    # Global chatter sub-controls (apply across ALL models without per-model config)
    global_hide_chatter = fields.Boolean(string='Hide Chatter Everywhere', help='Completely hide the chatter area globally.')
    global_hide_send_message = fields.Boolean(string='Hide Send Message Everywhere', help='Hide the Send Message button globally across the entire system.')
    global_hide_log_note = fields.Boolean(string='Hide Log Note Everywhere', help='Hide the Log Note button globally across the entire system.')
    global_hide_activities = fields.Boolean(string='Hide Activities Everywhere', help='Hide the Schedule Activity button globally across the entire system.')
    global_hide_followers = fields.Boolean(string='Hide Followers Everywhere', help='Hide the followers section (the user icons and Add Followers button) in the chatter globally.')
    # Global UI controls.  These complement the per-model controls below and
    # intentionally remain presentation controls unless a model/record rule
    # is also configured.
    global_hide_import = fields.Boolean(string='Hide Import Everywhere', help='Hide the Import records action globally.')
    global_hide_print = fields.Boolean(string='Hide Print Everywhere', help='Hide the Print contextual menu globally.')
    global_hide_action = fields.Boolean(string='Hide Action Everywhere', help='Hide the Action contextual menu globally.')
    global_hide_export = fields.Boolean(string='Hide Export Everywhere', help='Hide the Export records action globally.')
    global_hide_spreadsheet = fields.Boolean(string='Hide Spreadsheet Everywhere', help='Hide the Insert in Spreadsheet action globally.')
    global_hide_filters = fields.Boolean(string='Hide Filters Everywhere', help='Hide the Filters menu in the search bar globally.')
    global_hide_groupby = fields.Boolean(string='Hide Group By Everywhere', help='Hide the Group By menu in the search bar globally.')
    global_hide_custom_filter = fields.Boolean(
        string='Hide Custom Filter Everywhere',
        help='Hide the "Custom Filter..." option in the search bar globally.')
    global_hide_custom_group = fields.Boolean(
        string='Hide Custom Group Everywhere',
        help='Hide the "Custom Group" option in the search bar globally.')
    global_hide_favorites = fields.Boolean(string='Hide Favorites Everywhere', help='Hide the Favorites menu in the search bar globally.')
    global_hide_searchbar = fields.Boolean(string='Hide Search Bar Everywhere', help='Hide the top right search bar globally.')
    global_hide_search_panel = fields.Boolean(string='Hide Left Search Panel Everywhere', help='Hide the left-side search panel globally.')
    global_hide_add_property = fields.Boolean(string='Hide Add Property Everywhere', help='Hide the Add a Property button globally.')
    global_hide_delete = fields.Boolean(string='Hide Delete Everywhere', help='Hide the Delete action globally.')
    global_hide_filter_delete = fields.Boolean(
        string='Hide Delete on Saved Filters',
        help='Prevent targeted users from deleting saved filters, group-by and favorites.')
    global_hide_attachments = fields.Boolean(string='Hide Chatter Attachments Everywhere', help='Hide the attachment paperclip icon in the chatter globally.')
    global_hide_chatter_search = fields.Boolean(string='Hide Chatter Search Everywhere', help='Hide the search functionality inside the chatter globally.')
    block_module_management = fields.Boolean(
        string='Block Module Install / Update / Uninstall',
        help='Prevent targeted users from changing installed applications.')
    global_element_ids = fields.One2many(
        'access.management.global.element', 'profile_id',
        string='Global Hidden Buttons / Tabs / Links',
        help='Buttons, tabs, and links to hide across all models.')

    # Apply automatically to users of a given type (covers "default new user" rules)
    apply_new_internal = fields.Boolean(
        string='All Internal Users',
        help="Apply this profile to every internal user (current and future).")
    apply_new_portal = fields.Boolean(
        string='All Portal Users',
        help="Apply this profile to every portal user (current and future).")

    # Scheduling: time & timezone based access
    date_start = fields.Datetime(string='Active From')
    date_end = fields.Datetime(string='Active Until')
    tz = fields.Selection(_tz_selection, string='Timezone', default=lambda self: self.env.user.tz or 'UTC')
    time_from = fields.Float(string='Daily From', help="Daily active window start (hour, in the timezone above).")
    time_to = fields.Float(string='Daily To', help="Daily active window end (hour). An end before the start continues overnight; 0 means midnight.")

    # Profile-level user controls
    password_expiry_days = fields.Integer(
        string='Password Expiry (days)',
        help="Force targeted users to reset their password after this many days. 0 = never.")
    restrict_developer_mode = fields.Boolean(string='Disable Developer Mode')
    global_prevent_login = fields.Boolean(
        string='Prevent Login for All',
        help="Block login for all users targeted by this profile.")
    hide_systray_keys = fields.Char(
        string='Hidden Systray Items',
        help="Comma-separated systray registry keys to hide "
             "(e.g. access_management_ai.SwitchUserMenu, mail.messaging_menu, SwitchCompanyMenu).")

    model_access_ids = fields.One2many('access.management.model', 'rule_id', string='Model Restrictions')
    field_access_ids = fields.One2many('access.management.field', 'rule_id', string='Field Restrictions')
    element_access_ids = fields.One2many('access.management.element', 'rule_id', string='UI Elements')
    model_restriction_count = fields.Integer(compute='_compute_restriction_counts')
    field_restriction_count = fields.Integer(compute='_compute_restriction_counts')
    element_restriction_count = fields.Integer(compute='_compute_restriction_counts')
    menu_count = fields.Integer(string='# Menus', compute='_compute_restriction_counts')
    action_count = fields.Integer(string='# Actions', compute='_compute_restriction_counts')
    report_count = fields.Integer(string='# Reports', compute='_compute_restriction_counts')
    user_count = fields.Integer(string='# Users', compute='_compute_restriction_counts')
    group_count = fields.Integer(string='# Groups', compute='_compute_restriction_counts')
    custom_group_count = fields.Integer(string='# Access Groups', compute='_compute_restriction_counts')
    has_schedule = fields.Boolean(compute='_compute_restriction_counts')
    kanban_accent = fields.Selection(
        [
            ('active', 'Active'),
            ('readonly', 'Read-only'),
            ('blocked', 'Login Blocked'),
            ('scheduled', 'Scheduled'),
            ('archived', 'Archived'),
        ],
        compute='_compute_restriction_counts',
    )

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        from odoo.exceptions import ValidationError
        for rec in self:
            if rec.date_start and rec.date_end and rec.date_end < rec.date_start:
                raise ValidationError("Invalid validity period: 'Active Until' date must be greater than or equal to 'Active From' date.")

    @api.constrains('time_from', 'time_to')
    def _check_times(self):
        from odoo.exceptions import ValidationError
        for rec in self:
            if rec.time_from or rec.time_to:
                if rec.time_from < 0 or rec.time_from > 24 or rec.time_to < 0 or rec.time_to > 24:
                    raise ValidationError("Time must be between 0 and 24 hours.")

    @api.depends(
        'model_access_ids', 'field_access_ids', 'element_access_ids',
        'menu_ids', 'report_ids', 'action_ids', 'server_action_ids',
        'client_action_ids', 'url_action_ids',
        'user_ids', 'group_ids', 'custom_group_ids',
        'active', 'readonly', 'global_prevent_login',
        'date_start', 'date_end', 'time_from', 'time_to',
    )
    def _compute_restriction_counts(self):
        model_data = self.env['access.management.model']._read_group(
            [('rule_id', 'in', self.ids)], ['rule_id'], ['__count']
        )
        model_counts = {rule.id: count for rule, count in model_data}

        field_data = self.env['access.management.field']._read_group(
            [('rule_id', 'in', self.ids)], ['rule_id'], ['__count']
        )
        field_counts = {rule.id: count for rule, count in field_data}

        element_data = self.env['access.management.element']._read_group(
            [('rule_id', 'in', self.ids)], ['rule_id'], ['__count']
        )
        element_counts = {rule.id: count for rule, count in element_data}

        for rule in self:
            rule.model_restriction_count = model_counts.get(rule.id, 0)
            rule.field_restriction_count = field_counts.get(rule.id, 0)
            rule.element_restriction_count = element_counts.get(rule.id, 0)
            rule.menu_count = len(rule.menu_ids)
            rule.action_count = (
                len(rule.action_ids)
                + len(rule.server_action_ids)
                + len(rule.client_action_ids)
                + len(rule.url_action_ids)
            )
            rule.report_count = len(rule.report_ids)
            rule.user_count = len(rule.user_ids)
            rule.group_count = len(rule.group_ids)
            rule.custom_group_count = len(rule.custom_group_ids)
            rule.has_schedule = bool(
                rule.date_start or rule.date_end or rule.time_from or rule.time_to
            )
            if not rule.active:
                rule.kanban_accent = 'archived'
            elif rule.global_prevent_login:
                rule.kanban_accent = 'blocked'
            elif rule.readonly:
                rule.kanban_accent = 'readonly'
            elif rule.has_schedule:
                rule.kanban_accent = 'scheduled'
            else:
                rule.kanban_accent = 'active'

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @api.model
    @api.ormcache('uid', 'tuple(self.env.companies.ids)')
    def _rule_ids_for_user(self, uid):
        """ Ids of active rules applying to ``uid`` in the current companies
        (schedule is evaluated later, outside the cache). """
        user = self.env['res.users'].browse(uid)
        group_ids = user._get_group_ids()
        custom_group_ids = self.env['access.management.group'].sudo().search([('user_ids', 'in', uid)]).ids
        ors = [('user_ids', 'in', uid), ('group_ids', 'in', list(group_ids))]
        if custom_group_ids:
            ors.append(('custom_group_ids', 'in', custom_group_ids))
        if user._is_internal():
            ors.append(('apply_new_internal', '=', True))
        if user.sudo().share:
            ors.append(('apply_new_portal', '=', True))
        domain = ['|'] * (len(ors) - 1) + ors
        rules = self.sudo().search(domain)
        company_ids = set(self.env.companies.ids)
        result = []
        for rule in rules:
            if rule.company_ids and not (set(rule.company_ids.ids) & company_ids):
                continue
            result.append(rule.id)
        return tuple(result)

    def _is_schedule_active(self):
        """ Whether the profile's time/date window currently allows it. """
        self.ensure_one()
        now = fields.Datetime.now()
        if self.date_start and now < self.date_start:
            return False
        if self.date_end and now > self.date_end:
            return False
        if self.time_from or self.time_to:
            tz = pytz.timezone(self.tz) if self.tz else pytz.UTC
            local = pytz.UTC.localize(now).astimezone(tz)
            hour = local.hour + local.minute / 60.0
            lo, hi = self.time_from, self.time_to or 24.0
            if lo <= hi:
                if not (lo <= hour <= hi):
                    return False
            elif hour < lo and hour > hi:  # window crosses midnight
                return False
        return True

    @api.model
    def _rules_for_user(self, uid=None):
        """ Recordset of active rules applying to the given (or current) user,
        filtered by their schedule (evaluated per call, never cached). """
        uid = uid or self.env.uid
        rules = self.sudo().browse(self._rule_ids_for_user(uid))
        return rules.filtered(lambda r: r._is_schedule_active())

    _ACTION_HIDE_FIELDS = (
        'report_ids',
        'action_ids',
        'server_action_ids',
        'client_action_ids',
        'url_action_ids',
    )

    @api.model
    def _hidden_action_ids_for_user(self, uid=None, model_name=None, action_field=None):
        """IDs of reports/actions hidden for the user.

        Rule-level Hide Reports & Actions always apply. Per-model lines apply
        when ``model_name`` matches that line (or all model-line selections when
        ``model_name`` is omitted — used for direct action load checks).
        """
        rules = self._rules_for_user(uid)
        if not rules:
            return set()
        fields = (action_field,) if action_field else self._ACTION_HIDE_FIELDS
        hidden = set()
        for field_name in fields:
            hidden.update(getattr(rules, field_name).ids)
            lines = rules.model_access_ids
            if model_name:
                lines = lines.filtered(lambda l, m=model_name: l.model_name == m)
            for line in lines:
                hidden.update(getattr(line, field_name).ids)
        return hidden

    # ------------------------------------------------------------------
    # Cron: auto-revoke expired profiles
    # ------------------------------------------------------------------
    @api.model
    def _cron_revoke_expired(self):
        expired = self.search([('active', '=', True), ('date_end', '!=', False),
                               ('date_end', '<', fields.Datetime.now())])
        if expired:
            expired.write({'active': False})

    # ------------------------------------------------------------------
    # Cache invalidation
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            reason = vals.pop('audit_reason', '')
            if reason:
                self = self.with_context(audit_reason=reason)
        records = super().create(vals_list)
        audit_vals = []
        for rec in records:
            if rec.user_ids:
                users_str = ", ".join(rec.user_ids.mapped('name'))
                audit_vals.append({
                    'action': 'grant',
                    'model_name': 'Access Profile',
                    'record_name': rec.name,
                    'new_value': f"Granted profile to: {users_str}",
                    'reason': self.env.context.get('audit_reason', ''),
                })
        if audit_vals:
            self.env['access.audit.log'].create(audit_vals)
        self.env.transaction.invalidate_ormcache()
        self.env.transaction.invalidate_access_cache()
        return records

    def write(self, vals):
        # audit_reason is a non-stored UI field; do not read it as a singleton
        # when write() is called on a multi-record set.
        reason = vals.pop('audit_reason', '') or self.env.context.get('audit_reason', '')
        previous = {rec.id: (rec.user_ids, rec.active) for rec in self}
        
        res = super().write(vals)
        
        audit_vals = []
        for rec in self:
            old_users, old_active = previous[rec.id]
            new_users = rec.user_ids
            new_active = rec.active
            
            added = new_users - old_users
            removed = old_users - new_users
            
            if added:
                audit_vals.append({
                    'action': 'grant',
                    'model_name': 'Access Profile',
                    'record_name': rec.name,
                    'new_value': f"Granted profile to: {', '.join(added.mapped('name'))}",
                    'reason': reason,
                })
            if removed:
                audit_vals.append({
                    'action': 'revoke',
                    'model_name': 'Access Profile',
                    'record_name': rec.name,
                    'previous_value': f"Revoked profile from: {', '.join(removed.mapped('name'))}",
                    'reason': reason,
                })
            if old_active and not new_active:
                audit_vals.append({
                    'action': 'revoke',
                    'model_name': 'Access Profile',
                    'record_name': rec.name,
                    'previous_value': "Profile was Active",
                    'new_value': "Profile Archived",
                    'reason': reason,
                })
            elif not old_active and new_active:
                audit_vals.append({
                    'action': 'grant',
                    'model_name': 'Access Profile',
                    'record_name': rec.name,
                    'previous_value': "Profile was Archived",
                    'new_value': "Profile Unarchived",
                    'reason': reason,
                })
        
        if audit_vals:
            self.env['access.audit.log'].create(audit_vals)

        self.env.transaction.invalidate_ormcache()
        self.env.transaction.invalidate_access_cache()
        return res

    def unlink(self):
        res = super().unlink()
        self.env.transaction.invalidate_ormcache()
        self.env.transaction.invalidate_access_cache()
        return res


class AccessManagementModel(models.Model):
    _name = 'access.management.model'
    _description = 'Access Management - Model Restriction'

    rule_id = fields.Many2one('access.management', required=True, ondelete='cascade', index=True)
    model_id = fields.Many2one('ir.model', string='Model', required=True, ondelete='cascade')
    model_name = fields.Char(related='model_id.model', store=True, string='Model Name', index=True)

    # Hard (server-enforced) CRUD. Unchecking denies the operation.
    perm_create = fields.Boolean(string='Create', default=True)
    perm_write = fields.Boolean(string='Edit', default=True)
    perm_unlink = fields.Boolean(string='Delete', default=True)

    @api.onchange('model_id')
    def _onchange_model_id(self):
        for rec in self:
            rec.domain_read = False
            rec.domain_write = False
            rec.domain_create = False
            rec.domain_unlink = False
            rec.date_filter_field = False
            rec.date_filter_period = False
            rec.hidden_filter_items = False
            rec.hidden_groupby_items = False

    # UI-level toggles
    allow_archive = fields.Boolean(string='Archive', default=True)
    allow_duplicate = fields.Boolean(string='Duplicate', default=True)
    allow_export = fields.Boolean(string='Export', default=True)
    hide_import_button = fields.Boolean(string='Hide Import')
    hide_spreadsheet_button = fields.Boolean(string='Hide Insert in Spreadsheet')
    hide_print = fields.Boolean(string='Hide Print', help='Hide the Print contextual menu for this model.')
    hide_action = fields.Boolean(string='Hide Action', help='Hide the Action contextual menu for this model.')

    # View-type hides
    hide_tree = fields.Boolean(string='Hide List View', help='Hide the List view for this model completely.')
    hide_form = fields.Boolean(string='Hide Form View', help='Hide the Form view for this model completely.')
    hide_kanban = fields.Boolean(string='Hide Kanban View', help='Hide the Kanban view for this model completely.')
    hide_calendar = fields.Boolean(string='Hide Calendar View', help='Hide the Calendar view for this model completely.')
    hide_pivot = fields.Boolean(string='Hide Pivot View')
    hide_graph = fields.Boolean(string='Hide Graph View')
    hide_gantt = fields.Boolean(string='Hide Gantt View')
    hide_map = fields.Boolean(string='Hide Map View')
    hide_activity = fields.Boolean(string='Hide Activity View')
    hide_hierarchy = fields.Boolean(string='Hide Hierarchy View')

    def _hidden_view_types(self):
        """ Set of view-mode names this line hides. """
        self.ensure_one()
        mapping = {
            'list': self.hide_tree, 'form': self.hide_form, 'kanban': self.hide_kanban,
            'calendar': self.hide_calendar, 'pivot': self.hide_pivot,
            'graph': self.hide_graph, 'gantt': self.hide_gantt,
            'map': self.hide_map, 'activity': self.hide_activity,
            'hierarchy': self.hide_hierarchy,
        }
        return {view for view, hidden in mapping.items() if hidden}

    # Search / navigation controls
    hide_searchbar = fields.Boolean(string='Hide Search Bar', help='Hide the entire search bar above this model.')
    hide_filters = fields.Boolean(string='Hide Filters', help='Hide the Filters menu in the search bar.')
    hide_groupby = fields.Boolean(string='Hide Group By', help='Hide the Group By menu in the search bar.')
    hide_custom_filter = fields.Boolean(
        string='Hide Custom Filter',
        help='Hide the "Custom Filter..." option in the search bar for this model.')
    hide_custom_group = fields.Boolean(
        string='Hide Custom Group',
        help='Hide the "Custom Group" option in the search bar for this model.')
    hide_favorites = fields.Boolean(string='Hide Favorites', help='Hide the Favorites menu in the search bar.')
    hide_search_panel = fields.Boolean(string='Hide Left Search Panel', help='Hide the left-side search panel.')
    hide_add_property = fields.Boolean(string='Hide Add Property', help='Hide the Add a Property button on this model.')
    hidden_filter_items = fields.Char(
        string='Hide Specific Filters',
        help='Comma-separated technical names (or labels) of Filters menu items to hide for this model.')
    hidden_groupby_items = fields.Char(
        string='Hide Specific Groups',
        help='Comma-separated field names (or labels) of Group By menu items to hide for this model.')

    # Per-model chatter
    chatter_hide = fields.Boolean(string='Hide Chatter', help='Completely hide the chatter area on this model.')
    chatter_hide_send_message = fields.Boolean(string='Hide Send Message', help='Hide the Send Message button in the chatter on all models.')
    chatter_hide_log_note = fields.Boolean(string='Hide Log Note', help='Hide the Log Note button in the chatter on all models.')
    chatter_hide_activities = fields.Boolean(string='Hide Activities', help='Hide the Schedule Activity button in the chatter on all models.')
    chatter_hide_followers = fields.Boolean(string='Hide Followers', help='Hide the followers section (the user icons and Add Followers button) in the chatter.')
    chatter_hide_attachments = fields.Boolean(string='Hide Attachments', help='Hide the attachment paperclip icon in the chatter on this model.')
    chatter_hide_search = fields.Boolean(string='Hide Search Messages', help='Hide the search functionality inside the chatter on this model.')

    # Record-level domains (record rules)
    domain_read = fields.Char(
        string='Read Domain',
        help="Odoo domain expression restricting which records are visible. "
             "Use 'user.id' or 'EU' for the current user, e.g. [('user_id','=',user.id)]. "
             "Available context: user, uid, time, company_id, company_ids.")
    domain_write = fields.Char(
        string='Write Domain',
        help="Domain restricting which records can be edited. Same context as Read Domain.")
    domain_create = fields.Char(
        string='Create Domain',
        help="Domain restricting record creation. Same context as Read Domain.")
    domain_unlink = fields.Char(
        string='Delete Domain',
        help="Domain restricting record deletion. Same context as Read Domain.")
    date_filter_field_id = fields.Many2one(
        'ir.model.fields', string='Date Filter Field',
        domain="[('model_id', '=', model_id), ('ttype', 'in', ('date', 'datetime'))]")
    date_filter_field = fields.Char(related='date_filter_field_id.name', store=True, string='Date Filter Field Name')
    date_filter_period = fields.Selection([
        ('today', 'Today'), ('yesterday', 'Yesterday'),
        ('this_week', 'This Week'), ('last_week', 'Last Week'),
        ('this_month', 'This Month'), ('last_month', 'Last Month'),
        ('this_year', 'This Year'), ('last_year', 'Last Year'),
    ], string='Date Filter Period')
    hierarchy_field_id = fields.Many2one(
        'ir.model.fields', string='Hierarchy Parent Field',
        domain="[('model_id', '=', model_id), ('ttype', '=', 'many2one')]")
    hierarchy_field = fields.Char(related='hierarchy_field_id.name', store=True, string='Hierarchy Parent Field Name')
    hierarchy_user_field_id = fields.Many2one(
        'ir.model.fields', string='Hierarchy User Field',
        domain="[('model_id', '=', model_id), ('ttype', '=', 'many2one'), ('relation', '=', 'res.users')]")
    hierarchy_user_field = fields.Char(related='hierarchy_user_field_id.name', store=True, string='Hierarchy User Field Name')
    hierarchy_mode = fields.Selection([
        ('descendants', 'User Record and Descendants'),
        ('ancestors', 'User Record and Ancestors'),
    ], string='Hierarchy Scope')
    soft_restrict = fields.Boolean(
        string='Soft Restrict',
        help="Apply the record domains only to this model, without cascading to inherited/parent models.")
    warn_mode = fields.Boolean(
        string='Warn Instead of Block',
        help="When enabled, restricted CRUD operations show a warning notification instead of "
             "hard-blocking. The user can still proceed after acknowledging the warning.")
    warn_message = fields.Char(
        string='Warning Message',
        help="Custom warning message shown when the user attempts a restricted operation. "
             "Leave empty for the default message.")

    # Per-model reports / actions (same capability as rule-level Hide Reports & Actions)
    report_ids = fields.Many2many(
        'ir.actions.report',
        'access_management_model_report_rel', 'model_line_id', 'report_id',
        string='Hidden Reports',
        help='Hide specific reports (Print menu) for this model.')
    action_ids = fields.Many2many(
        'ir.actions.act_window',
        'access_management_model_action_rel', 'model_line_id', 'action_id',
        string='Hidden Window Actions',
        help='Hide specific window actions (Action menu) for this model.')
    server_action_ids = fields.Many2many(
        'ir.actions.server',
        'access_management_model_server_action_rel', 'model_line_id', 'action_id',
        string='Hidden Server Actions',
        help='Hide specific server actions for this model.')
    client_action_ids = fields.Many2many(
        'ir.actions.client',
        'access_management_model_client_action_rel', 'model_line_id', 'action_id',
        string='Hidden Client Actions',
        help='Hide specific client actions for this model.')
    url_action_ids = fields.Many2many(
        'ir.actions.act_url',
        'access_management_model_url_action_rel', 'model_line_id', 'action_id',
        string='Hidden URL Actions',
        help='Hide specific URL actions for this model.')

    _rule_model_uniq = models.Constraint('unique(rule_id, model_id)', 'A model can only be configured once per access rule.')

    @api.model
    def _split_search_item_keys(self, value):
        if not value:
            return []
        return [part.strip() for part in str(value).split(',') if part.strip()]

    @api.model
    def get_search_menu_items(self, model_id, item_type='filter'):
        """Return Filters or Group By items defined on the model's search view.

        Each entry is ``{key, label}`` where ``key`` is the stable identifier used
        in ``hidden_filter_items`` / ``hidden_groupby_items`` (technical name,
        field name, or label fallback).
        """
        if not model_id:
            return []
        model = self.env['ir.model'].browse(model_id)
        if not model.exists() or model.model not in self.env:
            return []
        Model = self.env[model.model]
        try:
            arch_data = Model._get_view(view_type='search')
            arch = arch_data[0] if isinstance(arch_data, tuple) else arch_data
        except Exception:  # noqa: BLE001
            try:
                views = Model.get_views([(False, 'search')], options={})
                arch = (views.get('views') or {}).get('search', {}).get('arch')
            except Exception:  # noqa: BLE001
                return []
        if arch is None:
            return []
        from lxml import etree
        if isinstance(arch, str):
            try:
                root = etree.fromstring(arch)
            except etree.XMLSyntaxError:
                return []
        else:
            root = arch

        fields_by_name = {f.name: f for f in self.env['ir.model.fields'].sudo().search([
            ('model', '=', model.model),
        ])}
        want_groupby = item_type in ('groupby', 'group', 'groupBy')
        items = []
        seen = set()

        for node in root.xpath('.//filter[not(ancestor::searchpanel)]'):
            invisible = (node.get('invisible') or '').strip().lower()
            if invisible in ('1', 'true'):
                continue
            context = node.get('context') or ''
            group_by_field = None
            if 'group_by' in context:
                try:
                    from odoo.tools.safe_eval import safe_eval
                    ctx = safe_eval(context, {'uid': self.env.uid, 'context': {}})
                    raw = ctx.get('group_by') if isinstance(ctx, dict) else None
                    if isinstance(raw, str) and raw:
                        group_by_field = raw.split(':')[0]
                except Exception:  # noqa: BLE001
                    # Best-effort parse: group_by':'field or group_by": "field
                    import re
                    match = re.search(r"['\"]group_by['\"]\s*:\s*['\"]([^'\"]+)['\"]", context)
                    if match:
                        group_by_field = match.group(1).split(':')[0]

            is_groupby = bool(group_by_field)
            if want_groupby != is_groupby:
                continue

            string = node.get('string') or ''
            name = node.get('name') or ''
            if is_groupby:
                key = group_by_field or name or string
                field = fields_by_name.get(group_by_field)
                label = string or (field.field_description if field else group_by_field) or key
            else:
                key = name or string
                if not key:
                    domain = node.get('domain') or ''
                    if not domain or domain == '[]':
                        continue
                    key = string or domain[:64]
                label = string or name or key

            if not key or key in seen:
                continue
            seen.add(key)
            items.append({'key': key, 'label': label})

        return items

    @api.constrains('domain_read', 'domain_write', 'domain_create', 'domain_unlink')
    def _check_domain_syntax(self):
        from odoo.tools.safe_eval import safe_eval, time
        from odoo.fields import Domain
        from odoo.exceptions import ValidationError
        # A dummy eval context to just test syntax compilation
        dummy_context = {
            'user': self.env.user,
            'uid': self.env.uid,
            'EU': self.env.uid,
            'time': time,
            'company_id': self.env.company.id,
            'company_ids': self.env.companies.ids,
        }
        for record in self:
            for field in ['domain_read', 'domain_write', 'domain_create', 'domain_unlink']:
                expr = getattr(record, field)
                if expr:
                    try:
                        Domain(safe_eval(expr, dummy_context)).optimize(self.env[record.model_name])
                    except Exception as e:
                        raise ValidationError(
                            f"Invalid domain syntax in {field} for model {record.model_name}:\n{expr}\nError: {e}"
                        )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        self.env.transaction.invalidate_ormcache()
        self.env.transaction.invalidate_access_cache()
        return records

    def write(self, vals):
        res = super().write(vals)
        self.env.transaction.invalidate_ormcache()
        self.env.transaction.invalidate_access_cache()
        return res

    def unlink(self):
        res = super().unlink()
        self.env.transaction.invalidate_ormcache()
        self.env.transaction.invalidate_access_cache()
        return res


class AccessManagementField(models.Model):
    _name = 'access.management.field'
    _description = 'Access Management - Field Restriction'

    rule_id = fields.Many2one('access.management', required=True, ondelete='cascade', index=True)
    model_id = fields.Many2one('ir.model', string='Model', required=True, ondelete='cascade')
    model_name = fields.Char(related='model_id.model', store=True, string='Model Name')
    field_id = fields.Many2one(
        'ir.model.fields', string='Field', required=True, ondelete='cascade',
        domain="[('model_id', '=', model_id)]")
    field_name = fields.Char(related='field_id.name', store=True, string='Field Name', index=True)
    relation = fields.Char(related='field_id.relation', string='Relation Model Name')

    is_invisible = fields.Boolean(string='Invisible', help='Hide this field completely from the user interface.')
    is_readonly = fields.Boolean(string='Read-only')
    is_required = fields.Boolean(string='Required', help='Force this field to be required before saving.')

    invisible_condition = fields.Char(string='Invisible If', help="Domain condition, e.g. [('state', '=', 'done')]")
    readonly_condition = fields.Char(string='Read-only If', help="Domain condition, e.g. [('state', '=', 'done')]")
    required_condition = fields.Char(string='Required If', help="Domain condition, e.g. [('state', '=', 'done')]")

    remove_external_link = fields.Boolean(
        string='Remove Internal/External Link',
        help="Removes the open (internal link) button.")
    no_create = fields.Boolean(
        string='Disable Create/Create & Edit',
        help="Disable on-the-fly creation or creation features.")
    domain = fields.Char(
        string='Dropdown Domain',
        help="Restricts the selectable records or provides domain filtering.")
    domain_model_name = fields.Char(
        compute='_compute_domain_model_name',
        string='Domain Model Name')
    restrict_export = fields.Boolean(
        string='Exclude From Export',
        help="Remove this field from the export field list for users targeted by this rule.")

    @api.depends('relation', 'model_name')
    def _compute_domain_model_name(self):
        for rec in self:
            rec.domain_model_name = rec.relation or rec.model_name

    _rule_field_uniq = models.Constraint('unique(rule_id, field_id)', 'A field can only be configured once per access rule.')

    @api.onchange('model_id')
    def _onchange_model_id(self):
        for rec in self:
            rec.field_id = False
            rec.invisible_condition = False
            rec.readonly_condition = False
            rec.required_condition = False
            rec.domain = False

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        self.env.transaction.invalidate_ormcache()
        self.env.transaction.invalidate_access_cache()
        return records

    def write(self, vals):
        res = super().write(vals)
        self.env.transaction.invalidate_ormcache()
        self.env.transaction.invalidate_access_cache()
        return res

    def unlink(self):
        res = super().unlink()
        self.env.transaction.invalidate_ormcache()
        self.env.transaction.invalidate_access_cache()
        return res


class AccessManagementElement(models.Model):
    _name = 'access.management.element'
    _description = 'Access Management - UI Element'

    rule_id = fields.Many2one('access.management', required=True, ondelete='cascade', index=True)
    model_id = fields.Many2one('ir.model', string='Model', required=True, ondelete='cascade')
    model_name = fields.Char(related='model_id.model', store=True, string='Model Name', index=True)
    view_type = fields.Selection(
        [('form', 'Form'), ('list', 'List'), ('kanban', 'Kanban'),
         ('any', 'Any')], string='View', default='form', required=True)
    element_type = fields.Selection(
        [('button', 'Button'), ('page', 'Notebook Page / Tab'),
         ('field', 'Field Element'), ('kanban_link', 'Kanban Link')],
        string='Element Type', default='button', required=True)
    element_ref = fields.Char(
        string='Name / Label', required=True,
        help="Matches the node 'name' attribute or its visible string/label.")
    invisible_condition = fields.Char(
        string='Invisible If',
        help="Python expression; leave empty to always hide.")

    _rule_element_uniq = models.Constraint('unique(rule_id, model_id, view_type, element_type, element_ref)', 'An element can only be configured once per model and view type per access rule.')

    @api.onchange('model_id', 'view_type', 'element_type')
    def _onchange_model_id(self):
        for rec in self:
            rec.element_ref = False
            rec.invisible_condition = False

    def action_open_selector(self):
        self.ensure_one()
        view_type = self.view_type if self.view_type != 'any' else 'form'
        arch_data = self.env[self.model_name]._get_view(view_type=view_type)
        if isinstance(arch_data, tuple):
            arch = arch_data[0] # Older Odoo or some cases
        elif isinstance(arch_data, dict):
            arch = arch_data.get('arch', '')
        else:
            arch = arch_data.arch
        
        import lxml.etree as ET
        if isinstance(arch, str):
            tree = ET.fromstring(arch)
        else:
            tree = arch
        
        choices = []
        for btn in tree.xpath('.//button'):
            name = btn.get('name')
            if not name: continue
            label = btn.get('string', '')
            choices.append((0, 0, {'name': name, 'label': label, 'element_type': 'button'}))
            
        for page in tree.xpath('.//page'):
            name = page.get('name')
            if not name: continue
            label = page.get('string', '')
            choices.append((0, 0, {'name': name, 'label': label, 'element_type': 'page'}))
            
        wizard = self.env['access.element.wizard'].create({
            'element_id': self.id,
            'choice_ids': choices
        })
        return {
            'type': 'ir.actions.act_window',
            'name': 'Select UI Element',
            'res_model': 'access.element.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }

    @api.model
    def get_ui_elements(self, model_id, view_type, element_type):
        import logging
        _logger = logging.getLogger(__name__)
        _logger.info("=== get_ui_elements called ===")
        _logger.info("model_id: %r, view_type: %r, element_type: %r", model_id, view_type, element_type)
        if not model_id:
            _logger.info("No model_id provided")
            return []
            
        if isinstance(model_id, dict):
            model_id = model_id.get('id') or model_id.get('value')
        if isinstance(model_id, (list, tuple)):
            model_id = model_id[0] if model_id else False
            
        if not model_id or not isinstance(model_id, int):
            _logger.info("Invalid model_id: %r", model_id)
            return []
            
        model_name = self.env['ir.model'].sudo().browse(int(model_id)).model
        if not model_name:
            _logger.info("Model name not found for id: %r", model_id)
            return []
        
        view_type = view_type if view_type != 'any' else 'form'
        try:
            arch_data = self.env[model_name]._get_view(view_type=view_type)
            if isinstance(arch_data, tuple):
                arch = arch_data[0]
            elif isinstance(arch_data, dict):
                arch = arch_data.get('arch', '')
            else:
                arch = arch_data.arch
                
            import lxml.etree as ET
            if isinstance(arch, str):
                tree = ET.fromstring(arch)
            else:
                tree = arch
        except Exception:
            return []
            
        choices = []
        if element_type in ('button', 'any', False):
            for btn in tree.xpath('.//button'):
                name = btn.get('name')
                if not name: continue
                label = btn.get('string', '')
                display = f"{label} ({name})" if label else name
                choices.append({'value': name, 'label': display})
                
        if element_type in ('page', 'any', False):
            for page in tree.xpath('.//page'):
                name = page.get('name')
                if not name: continue
                label = page.get('string', '')
                display = f"{label} ({name})" if label else name
                choices.append({'value': name, 'label': display})
                
        if element_type in ('kanban_link', 'any', False):
            for a in tree.xpath('.//a'):
                name = a.get('name') or a.get('type')
                if not name: continue
                display = f"Link ({name})"
                choices.append({'value': name, 'label': display})
                
        if element_type in ('field', 'any', False):
            for node in tree.xpath('.//field[@name]'):
                name = node.get('name')
                choices.append({'value': name, 'label': node.get('string') or name})

        unique_choices = []
        seen = set()
        for c in choices:
            if c['value'] not in seen:
                seen.add(c['value'])
                unique_choices.append(c)
                
        return unique_choices

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        self.env.transaction.invalidate_ormcache()
        self.env.transaction.invalidate_access_cache()
        return records

    def write(self, vals):
        res = super().write(vals)
        self.env.transaction.invalidate_ormcache()
        self.env.transaction.invalidate_access_cache()
        return res

    def unlink(self):
        res = super().unlink()
        self.env.transaction.invalidate_ormcache()
        self.env.transaction.invalidate_access_cache()
        return res

class AccessManagementGlobalElement(models.Model):
    _name = 'access.management.global.element'
    _description = 'Global Hidden Element'

    profile_id = fields.Many2one('access.management', required=True, ondelete='cascade', index=True)
    model_id = fields.Many2one('ir.model', string='Reference Model', required=True, ondelete='cascade', help="Select a model to populate the element dropdown. The restriction will still apply globally.")
    view_type = fields.Selection([
        ('form', 'Form'),
        ('list', 'List / Tree'),
        ('kanban', 'Kanban'),
        ('any', 'Any')], string='View', default='form', required=True)
    element_type = fields.Selection([
        ('button', 'Button'),
        ('page', 'Notebook Page / Tab'),
        ('kanban_link', 'Kanban Link'),
        ('any', 'Any')
    ], string='Element Type', default='button', required=True)
    element_ref = fields.Char(
        string='Technical Name', required=True,
        help="The 'name' attribute of the button, page, or link.")

    @api.onchange('model_id', 'view_type', 'element_type')
    def _onchange_model_id(self):
        for rec in self:
            rec.element_ref = False

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        self.env.transaction.invalidate_ormcache()
        self.env.transaction.invalidate_access_cache()
        return records

    def write(self, vals):
        res = super().write(vals)
        self.env.transaction.invalidate_ormcache()
        self.env.transaction.invalidate_access_cache()
        return res

    def unlink(self):
        res = super().unlink()
        self.env.transaction.invalidate_ormcache()
        self.env.transaction.invalidate_access_cache()
        return res
