# -*- coding: utf-8 -*-
# Copyright (C) NexGen Solutions
from odoo import api, fields, models

class AccessManagementGroup(models.Model):
    _name = 'access.management.group'
    _description = 'Access Management Custom Group'
    _order = 'name'
    
    name = fields.Char(string='Group Name', required=True)
    user_ids = fields.Many2many(
        'res.users',
        'access_management_group_res_users_rel',
        'access_management_group_id', 'res_users_id',
        string='Users', domain=[('share', '=', False)])
    user_count = fields.Integer(string='User Count', compute='_compute_user_count')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)

    @api.depends('user_ids')
    def _compute_user_count(self):
        for group in self:
            group.user_count = len(group.user_ids)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        self.env.transaction.invalidate_ormcache()
        self.env.transaction.invalidate_access_cache()
        return records

    def write(self, vals):
        result = super().write(vals)
        self.env.transaction.invalidate_ormcache()
        self.env.transaction.invalidate_access_cache()
        return result

    def unlink(self):
        result = super().unlink()
        self.env.transaction.invalidate_ormcache()
        self.env.transaction.invalidate_access_cache()
        return result
