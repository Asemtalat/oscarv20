# Copyright (C) NexGen Solutions
from odoo import Command, api, fields, models


def _user_group_field(env):
    """ Name of the writable Many2many on res.users that holds the user's
    *directly* assigned security groups. Modern Odoo renamed the historical
    ``groups_id`` to ``group_ids`` (with a computed transitive ``all_group_ids``);
    detect it so the role sync keeps working across versions. """
    Users = env['res.users']
    for name in ('group_ids', 'groups_id'):
        f = Users._fields.get(name)
        if f and f.type == 'many2many' and f.comodel_name == 'res.groups' \
                and f.store and not f.related:
            return name
    return 'groups_id'


class AccessRole(models.Model):
    """ A reusable bundle of security groups (a "role") that can be granted to
    many users at once - optionally only during a validity window. Assigning a
    role adds its groups to the user; removing it (or letting it expire) removes
    those groups again, while leaving the user's other groups untouched. """
    _name = 'access.role'
    _description = 'Security Role'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, name'

    name = fields.Char(required=True, translate=True, tracking=True)
    active = fields.Boolean(default=True, tracking=True)
    sequence = fields.Integer(default=10)
    comment = fields.Text(string='Description')
    color = fields.Integer(string='Color')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)

    group_ids = fields.Many2many(
        'res.groups', 'access_role_group_rel', 'role_id', 'group_id',
        string='Groups',
        help="Security groups granted to every user who has this role.")
    implied_role_ids = fields.Many2many(
        'access.role', 'access_role_implied_rel', 'role_id', 'implied_id',
        string='Included Roles',
        help="Other roles whose groups are also granted by this role.")

    line_ids = fields.One2many('access.role.line', 'role_id', string='Users')
    user_count = fields.Integer(string='# Users', compute='_compute_kanban_stats')
    active_user_count = fields.Integer(string='# Active Users', compute='_compute_kanban_stats')
    group_count = fields.Integer(string='# Groups', compute='_compute_kanban_stats')
    implied_count = fields.Integer(string='# Included Roles', compute='_compute_kanban_stats')
    effective_group_count = fields.Integer(
        string='# Effective Groups',
        compute='_compute_kanban_stats',
        help='Groups granted by this role including included roles.',
    )
    display_user_ids = fields.Many2many(
        'res.users',
        string='Assigned Users',
        compute='_compute_kanban_stats',
    )
    kanban_accent = fields.Selection(
        [
            ('active', 'Active'),
            ('assigned', 'Assigned'),
            ('nested', 'Includes Roles'),
            ('archived', 'Archived'),
        ],
        compute='_compute_kanban_stats',
    )

    @api.depends(
        'line_ids', 'line_ids.user_id', 'line_ids.date_from', 'line_ids.date_to',
        'group_ids', 'implied_role_ids', 'implied_role_ids.group_ids',
        'implied_role_ids.implied_role_ids', 'active',
    )
    def _compute_kanban_stats(self):
        today = fields.Date.context_today(self)
        line_data = self.env['access.role.line']._read_group(
            [('role_id', 'in', self.ids)], ['role_id'], ['__count']
        )
        line_counts = {role.id: count for role, count in line_data}
        for role in self:
            role.user_count = line_counts.get(role.id, 0)
            role.group_count = len(role.group_ids)
            role.implied_count = len(role.implied_role_ids)
            role.effective_group_count = len(role._get_all_group_ids())
            active_users = role.line_ids.filtered(lambda line: line._enabled(today)).mapped('user_id')
            role.active_user_count = len(active_users)
            role.display_user_ids = active_users
            if not role.active:
                role.kanban_accent = 'archived'
            elif role.implied_count:
                role.kanban_accent = 'nested'
            elif role.user_count:
                role.kanban_accent = 'assigned'
            else:
                role.kanban_accent = 'active'

    # ------------------------------------------------------------------
    def _get_all_roles(self):
        """ This role plus every (transitively) included role. """
        result = self.browse()
        todo = self.with_context(active_test=False)
        while todo:
            result |= todo
            todo = todo.implied_role_ids - result
        return result

    def _get_all_group_ids(self):
        """ All groups granted by this role, including those of included roles. """
        roles = self.browse()
        todo = self.filtered('active')
        while todo:
            roles |= todo
            todo = todo.implied_role_ids.filtered('active') - roles
        return roles.group_ids

    def _get_dependent_roles(self):
        """Include parent roles whose effective grants change with this role."""
        result = self.with_context(active_test=False)
        todo = result
        while todo:
            todo = self.with_context(active_test=False).search([
                ('implied_role_ids', 'in', todo.ids), ('id', 'not in', result.ids),
            ])
            result |= todo
        return result

    def _sync_users(self):
        """ Re-apply every affected user's group membership. """
        users = self._get_dependent_roles().line_ids.user_id
        if users:
            users._access_roles_sync_groups()

    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        roles = super().create(vals_list)
        roles._sync_users()
        return roles

    def write(self, vals):
        # Preserve affected users before included roles or assignments change.
        before_users = self._get_dependent_roles().line_ids.user_id
        res = super().write(vals)
        users = before_users | self._get_dependent_roles().line_ids.user_id
        users._access_roles_sync_groups()
        return res

    def unlink(self):
        users = self._get_dependent_roles().line_ids.user_id
        res = super().unlink()
        if users:
            users._access_roles_sync_groups()
        return res

    # ------------------------------------------------------------------
    def action_view_users(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.name,
            'res_model': 'res.users',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.line_ids.user_id.ids)],
        }


class AccessRoleLine(models.Model):
    _name = 'access.role.line'
    _description = 'Security Role Assignment'

    role_id = fields.Many2one('access.role', required=True, ondelete='cascade', index=True)
    user_id = fields.Many2one('res.users', string='User', required=True, ondelete='cascade', index=True, domain=[('share', '=', False)])
    date_from = fields.Date(string='From', help="Grant the role only from this date (inclusive).")
    date_to = fields.Date(string='To', help="Grant the role only until this date (inclusive).")
    is_enabled = fields.Boolean(string='Active Now', compute='_compute_is_enabled')

    _role_user_uniq = models.Constraint('unique(role_id, user_id)', 'A user can only be assigned a role once.')

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        from odoo.exceptions import ValidationError
        for rec in self:
            if rec.date_from and rec.date_to and rec.date_to < rec.date_from:
                raise ValidationError("Invalid validity period: 'To' date must be greater than or equal to 'From' date.")

    @api.depends('role_id.active', 'date_from', 'date_to')
    def _compute_is_enabled(self):
        today = fields.Date.context_today(self)
        for line in self:
            line.is_enabled = line._enabled(today)

    def _enabled(self, today=None):
        self.ensure_one()
        if not self.role_id.active:
            return False
        today = today or fields.Date.context_today(self)
        if self.date_from and today < self.date_from:
            return False
        if self.date_to and today > self.date_to:
            return False
        return True

    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            reason = vals.pop('audit_reason', '')
            if reason:
                self = self.with_context(audit_reason=reason)
        lines = super().create(vals_list)
        audit_vals = []
        for line in lines:
            audit_vals.append({
                'action': 'grant',
                'model_name': 'Access Role',
                'record_name': line.role_id.name,
                'target_user_id': line.user_id.id,
                'new_value': f"Assigned role to {line.user_id.name}",
                'reason': self.env.context.get('audit_reason', ''),
            })
        if audit_vals:
            self.env['access.audit.log'].create(audit_vals)
        lines.user_id._access_roles_sync_groups()
        return lines

    def write(self, vals):
        reason = vals.pop('audit_reason', '')
        before_users = self.user_id
        res = super().write(vals)
        audit_vals = []
        for line in self:
            if 'date_from' in vals or 'date_to' in vals:
                audit_vals.append({
                    'action': 'modify',
                    'model_name': 'Access Role',
                    'record_name': line.role_id.name,
                    'target_user_id': line.user_id.id,
                    'new_value': f"Updated dates to {line.date_from} -> {line.date_to}",
                    'reason': reason,
                })
        if audit_vals:
            self.env['access.audit.log'].create(audit_vals)
        (before_users | self.user_id)._access_roles_sync_groups()
        return res

    def unlink(self):
        audit_vals = []
        for line in self:
            audit_vals.append({
                'action': 'revoke',
                'model_name': 'Access Role',
                'record_name': line.role_id.name,
                'target_user_id': line.user_id.id,
                'previous_value': f"Revoked role from {line.user_id.name}",
                'reason': self.env.context.get('audit_reason', ''),
            })
        if audit_vals:
            self.env['access.audit.log'].create(audit_vals)
        users = self.user_id
        res = super().unlink()
        users._access_roles_sync_groups()
        return res
