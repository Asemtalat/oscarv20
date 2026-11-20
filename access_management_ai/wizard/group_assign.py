# Copyright (C) NexGen Solutions
from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError

from ..models.access_role import _user_group_field


class AccessGroupAssign(models.TransientModel):
    """ Apply security groups, roles and/or access profiles to many users at
    once (add / remove / replace). """
    _name = 'access.group.assign'
    _description = 'Mass Group / Role Assignment'

    user_ids = fields.Many2many('res.users', string='Users', required=True, domain=[('share', '=', False)])
    operation = fields.Selection(
        [('add', 'Add'), ('remove', 'Remove'), ('replace', 'Replace')],
        string='Operation', default='add', required=True,
        help="Add: grant the selection on top of what users already have.\n"
             "Remove: revoke the selection from the users.\n"
             "Replace: for groups, set exactly the selected groups.")
    group_ids = fields.Many2many('res.groups', string='Groups')
    role_ids = fields.Many2many('access.role', string='Roles')
    profile_ids = fields.Many2many('access.management', string='Access Rules')
    date_from = fields.Date(string='Role From')
    date_to = fields.Date(string='Role To')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get('active_model') == 'res.users' and self.env.context.get('active_ids'):
            res['user_ids'] = [Command.set(self.env.context['active_ids'])]
        return res

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for record in self:
            if record.date_from and record.date_to and record.date_from > record.date_to:
                raise UserError(_("Role 'To' date must be greater than or equal to 'From' date."))

    def _apply_groups(self):
        gfield = _user_group_field(self.env)
        if self.operation == 'replace':
            cmd = [Command.set(self.group_ids.ids)]
        elif self.operation == 'remove':
            cmd = [Command.unlink(g) for g in self.group_ids.ids]
        else:
            cmd = [Command.link(g) for g in self.group_ids.ids]
        self.user_ids.sudo().write({gfield: cmd})

    def _apply_roles(self):
        Line = self.env['access.role.line'].sudo()
        if self.operation == 'replace':
            lines_to_remove = Line.search([('user_id', 'in', self.user_ids.ids), ('role_id', 'not in', self.role_ids.ids)])
            lines_to_remove.unlink()
            
        for user in self.user_ids:
            for role in self.role_ids:
                line = Line.search([('user_id', '=', user.id), ('role_id', '=', role.id)], limit=1)
                if self.operation == 'remove':
                    line.unlink()
                elif not line:
                    Line.create({
                        'user_id': user.id, 'role_id': role.id,
                        'date_from': self.date_from, 'date_to': self.date_to,
                    })
                else:
                    line.write({'date_from': self.date_from, 'date_to': self.date_to})

    def _apply_profiles(self):
        Profile = self.env['access.management'].sudo()
        if self.operation == 'replace':
            all_profiles = Profile.search([('user_ids', 'in', self.user_ids.ids)])
            for profile in all_profiles:
                if profile not in self.profile_ids:
                    profile.write({'user_ids': [Command.unlink(u) for u in self.user_ids.ids]})
            
        for profile in self.profile_ids.sudo():
            if self.operation == 'remove':
                profile.write({'user_ids': [Command.unlink(u) for u in self.user_ids.ids]})
            else:
                profile.write({'user_ids': [Command.link(u) for u in self.user_ids.ids]})

    def action_apply(self):
        self.ensure_one()
        if not (self.group_ids or self.role_ids or self.profile_ids):
            raise UserError(_("Select at least one group, role or access rule to apply."))
        if self.group_ids:
            self._apply_groups()
        if self.role_ids:
            self._apply_roles()
        if self.profile_ids:
            self._apply_profiles()
        self.env.transaction.invalidate_ormcache()
        self.env.transaction.invalidate_access_cache()
        
        self.env['access.audit.log'].create({
            'action': 'workflow',
            'model_name': 'Mass Assignment Wizard',
            'record_name': 'AccessGroupAssign',
            'new_value': f"Executed {self.operation} operation on {len(self.user_ids)} users",
            'reason': 'Mass Assignment Wizard',
        })

        return {
            'type': 'ir.actions.act_window',
            'name': _('Affected Users'),
            'res_model': 'res.users',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.user_ids.ids)],
        }
