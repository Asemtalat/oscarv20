# Copyright (C) NexGen Solutions
from odoo import fields, models, tools


class AccessManagementReport(models.Model):
    _name = 'access.management.report'
    _description = 'Access Management Analysis'
    _auto = False
    _rec_name = 'model_id'
    _order = 'restriction_count desc, model_name'

    rule_id = fields.Many2one('access.management', string='Profile', readonly=True)
    model_id = fields.Many2one('ir.model', string='Model', readonly=True)
    model_name = fields.Char(string='Technical Name', readonly=True)

    # CRUD / operations (True = allowed)
    perm_create = fields.Boolean(string='Create Allowed', readonly=True)
    perm_write = fields.Boolean(string='Edit Allowed', readonly=True)
    perm_unlink = fields.Boolean(string='Delete Allowed', readonly=True)
    allow_archive = fields.Boolean(string='Archive Allowed', readonly=True)
    allow_duplicate = fields.Boolean(string='Duplicate Allowed', readonly=True)
    allow_export = fields.Boolean(string='Export Allowed', readonly=True)

    # UI hides
    hide_import = fields.Boolean(string='Hide Import', readonly=True)
    hide_print = fields.Boolean(string='Hide Print', readonly=True)
    hide_action = fields.Boolean(string='Hide Action', readonly=True)
    hide_list = fields.Boolean(string='Hide List', readonly=True)
    hide_form = fields.Boolean(string='Hide Form', readonly=True)
    hide_kanban = fields.Boolean(string='Hide Kanban', readonly=True)
    hide_chatter = fields.Boolean(string='Hide Chatter', readonly=True)
    has_domain = fields.Boolean(string='Has Domains', readonly=True)
    has_hierarchy = fields.Boolean(string='Has Hierarchy', readonly=True)
    soft_restrict = fields.Boolean(string='Soft Restrict', readonly=True)
    warn_mode = fields.Boolean(string='Warn Mode', readonly=True)

    field_count = fields.Integer(string='Field Rules', readonly=True)
    element_count = fields.Integer(string='UI Elements', readonly=True)
    restriction_count = fields.Integer(
        string='Restrictions',
        readonly=True,
        help="Number of restriction flags configured on this model in this profile.",
    )

    # Related profile context for richer cards
    rule_active = fields.Boolean(related='rule_id.active', string='Rule Active')
    rule_readonly = fields.Boolean(related='rule_id.readonly', string='Global Read-only')
    rule_prevent_login = fields.Boolean(related='rule_id.global_prevent_login', string='Prevent Login')
    rule_user_count = fields.Integer(related='rule_id.user_count', string='Rule Users')
    rule_menu_count = fields.Integer(related='rule_id.menu_count', string='Hidden Menus')

    severity = fields.Selection(
        [
            ('none', 'Full Access'),
            ('low', 'Light'),
            ('medium', 'Partial'),
            ('high', 'Heavy'),
        ],
        string='Severity',
        readonly=True,
    )
    blocked_ops_count = fields.Integer(string='Blocked Ops', readonly=True)
    hidden_views_count = fields.Integer(string='Hidden Views', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    sub.id,
                    sub.rule_id,
                    sub.model_id,
                    sub.model_name,
                    sub.perm_create,
                    sub.perm_write,
                    sub.perm_unlink,
                    sub.allow_archive,
                    sub.allow_duplicate,
                    sub.allow_export,
                    sub.hide_import,
                    sub.hide_print,
                    sub.hide_action,
                    sub.hide_list,
                    sub.hide_form,
                    sub.hide_kanban,
                    sub.hide_chatter,
                    sub.has_domain,
                    sub.has_hierarchy,
                    sub.soft_restrict,
                    sub.warn_mode,
                    sub.field_count,
                    sub.element_count,
                    sub.restriction_count,
                    sub.blocked_ops_count,
                    sub.hidden_views_count,
                    CASE
                        WHEN sub.restriction_count <= 0 THEN 'none'
                        WHEN sub.restriction_count < 3 THEN 'low'
                        WHEN sub.restriction_count < 5 THEN 'medium'
                        ELSE 'high'
                    END AS severity
                FROM (
                    SELECT
                        m.id AS id,
                        m.rule_id AS rule_id,
                        m.model_id AS model_id,
                        m.model_name AS model_name,
                        COALESCE(m.perm_create, TRUE) AS perm_create,
                        COALESCE(m.perm_write, TRUE) AS perm_write,
                        COALESCE(m.perm_unlink, TRUE) AS perm_unlink,
                        COALESCE(m.allow_archive, TRUE) AS allow_archive,
                        COALESCE(m.allow_duplicate, TRUE) AS allow_duplicate,
                        COALESCE(m.allow_export, TRUE) AS allow_export,
                        COALESCE(m.hide_import_button, FALSE) AS hide_import,
                        COALESCE(m.hide_print, FALSE) AS hide_print,
                        COALESCE(m.hide_action, FALSE) AS hide_action,
                        COALESCE(m.hide_tree, FALSE) AS hide_list,
                        COALESCE(m.hide_form, FALSE) AS hide_form,
                        COALESCE(m.hide_kanban, FALSE) AS hide_kanban,
                        COALESCE(m.chatter_hide, FALSE) AS hide_chatter,
                        (
                            (m.domain_read IS NOT NULL AND btrim(m.domain_read) <> '')
                            OR (m.domain_write IS NOT NULL AND btrim(m.domain_write) <> '')
                            OR (m.domain_create IS NOT NULL AND btrim(m.domain_create) <> '')
                            OR (m.domain_unlink IS NOT NULL AND btrim(m.domain_unlink) <> '')
                        ) AS has_domain,
                        (m.hierarchy_mode IS NOT NULL) AS has_hierarchy,
                        COALESCE(m.soft_restrict, FALSE) AS soft_restrict,
                        COALESCE(m.warn_mode, FALSE) AS warn_mode,
                        COALESCE(fc.field_count, 0) AS field_count,
                        COALESCE(ec.element_count, 0) AS element_count,
                        (
                            (NOT COALESCE(m.perm_create, TRUE))::int
                            + (NOT COALESCE(m.perm_write, TRUE))::int
                            + (NOT COALESCE(m.perm_unlink, TRUE))::int
                            + (NOT COALESCE(m.allow_archive, TRUE))::int
                            + (NOT COALESCE(m.allow_duplicate, TRUE))::int
                            + (NOT COALESCE(m.allow_export, TRUE))::int
                            + COALESCE(m.hide_import_button, FALSE)::int
                            + COALESCE(m.hide_spreadsheet_button, FALSE)::int
                            + COALESCE(m.hide_print, FALSE)::int
                            + COALESCE(m.hide_action, FALSE)::int
                            + COALESCE(m.hide_tree, FALSE)::int
                            + COALESCE(m.hide_form, FALSE)::int
                            + COALESCE(m.hide_kanban, FALSE)::int
                            + COALESCE(m.hide_calendar, FALSE)::int
                            + COALESCE(m.hide_searchbar, FALSE)::int
                            + COALESCE(m.hide_filters, FALSE)::int
                            + COALESCE(m.hide_groupby, FALSE)::int
                            + COALESCE(m.hide_custom_filter, FALSE)::int
                            + COALESCE(m.hide_custom_group, FALSE)::int
                            + COALESCE(m.hide_favorites, FALSE)::int
                            + COALESCE(m.hide_search_panel, FALSE)::int
                            + COALESCE(m.hide_add_property, FALSE)::int
                            + COALESCE(m.hide_hierarchy, FALSE)::int
                            + (CASE WHEN m.date_filter_period IS NOT NULL THEN 1 ELSE 0 END)
                            + (CASE WHEN m.hierarchy_mode IS NOT NULL THEN 1 ELSE 0 END)
                            + COALESCE(m.chatter_hide, FALSE)::int
                            + COALESCE(m.soft_restrict, FALSE)::int
                            + COALESCE(m.warn_mode, FALSE)::int
                        ) AS restriction_count,
                        (
                            (NOT COALESCE(m.perm_create, TRUE))::int
                            + (NOT COALESCE(m.perm_write, TRUE))::int
                            + (NOT COALESCE(m.perm_unlink, TRUE))::int
                            + (NOT COALESCE(m.allow_archive, TRUE))::int
                            + (NOT COALESCE(m.allow_duplicate, TRUE))::int
                            + (NOT COALESCE(m.allow_export, TRUE))::int
                        ) AS blocked_ops_count,
                        (
                            COALESCE(m.hide_tree, FALSE)::int
                            + COALESCE(m.hide_form, FALSE)::int
                            + COALESCE(m.hide_kanban, FALSE)::int
                        ) AS hidden_views_count
                    FROM access_management_model m
                    LEFT JOIN (
                        SELECT rule_id, model_id, COUNT(*) AS field_count
                        FROM access_management_field
                        GROUP BY rule_id, model_id
                    ) fc ON fc.rule_id = m.rule_id AND fc.model_id = m.model_id
                    LEFT JOIN (
                        SELECT rule_id, model_id, COUNT(*) AS element_count
                        FROM access_management_element
                        GROUP BY rule_id, model_id
                    ) ec ON ec.rule_id = m.rule_id AND ec.model_id = m.model_id
                ) sub
            )
        """ % (self._table,))
