# -*- coding: utf-8 -*-
import json
from datetime import datetime

from odoo import models, fields, api


class RequestSales(models.Model):
    _name = 'request.sales'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Request Sales'

    name = fields.Char(string='Name', required=True, default='New', copy=False)
    user_id = fields.Many2one(comodel_name='res.users', string='Responsible User', default=lambda self: self.env.user)
    scheduled_date = fields.Date(default=datetime.today(), required=True)
    location_id = fields.Many2one(comodel_name='stock.location')
    location_domain = fields.Char(compute='_compute_location_domain')
    has_second_approve = fields.Boolean()
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], default='draft')

    can_edit = fields.Boolean(compute='_compute_can_edit')

    @api.depends('state', 'request_lines.purchase_id')
    def _compute_can_edit(self):
        for rec in self:
            rec.can_edit = (
                    rec.state == 'draft'
                    or
                    (
                            rec.state != 'draft'
                            and
                            self.env.user.has_group('raval_request_sales.group_second_approval')
                    )
                    and
                    len(rec.request_lines.purchase_id.ids) == 0
            )

    def action_submit(self):
        if self.has_second_approve:
            self.state = 'submitted'
        else:
            self.state = 'approved'

    def action_second_approve(self):
        self.state = 'approved'

    request_lines = fields.One2many(comodel_name='request.sales.lines', inverse_name='request_id')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals.get('name') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('request.sales')
        return super(RequestSales, self).create(vals_list)

    @api.depends('user_id')
    def _compute_location_domain(self):
        for rec in self:
            rec.location_domain = json.dumps([
                ('id', 'in', rec.user_id.allowed_locations_ids.ids)
            ])

    def action_create_po_for_lines(self):
        self.request_lines.action_create_po()

    def action_open_purchase(self):
        return {
            'name': 'Purchase Order',
            'view_mode': 'list,form',
            'res_model': 'purchase.order',
            'type': 'ir.actions.act_window',
            'target': 'current',
            'domain': [('id', 'in', self.request_lines.purchase_id.ids)],
        }
