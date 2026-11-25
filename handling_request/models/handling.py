# -*- coding: utf-8 -*-

from datetime import datetime
from odoo.exceptions import UserError
from odoo import models, fields, api, _


class RequestHandling(models.Model):
    _name = 'request.handling'
    _description = 'Handling Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Reference', required=True, copy=False, default='New')
    user_id = fields.Many2one('res.users', string='Responsible User', default=lambda self: self.env.user)
    scheduled_date = fields.Date(string='Scheduled Date')
    location_id = fields.Many2one(comodel_name='stock.location')
    request_sales_id = fields.Many2one(comodel_name='request.sales', copy=False)
    handling_line_ids = fields.One2many('request.handling.line', 'handling_id', string='Request Lines')
    picking_id = fields.Many2one(comodel_name="stock.picking", string="Internal Transfer", copy=False)
    adjustment_ids = fields.One2many(comodel_name="handle.adjustment", inverse_name="handle_id", copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals.get('name') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('request.handling')
        return super(RequestHandling, self).create(vals_list)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], string='Status', default='draft', tracking=True)

    def action_submit(self):
        self.state = 'submitted'

    def action_approve(self):
        self.state = 'approved'

    def action_reject(self):
        self.state = 'rejected'

    def action_create_internal_transfer(self):
        """
        Create an internal transfer in stock.picking.
        """
        stock_picking_obj = self.env['stock.picking']
        stock_move_obj = self.env['stock.move']

        # Get the main location
        source_location = self.env['stock.location'].search([('is_main_location', '=', True)], limit=1)
        if not source_location:
            raise UserError("No main location found.")

        # Create stock.picking
        picking_vals = {
            'location_id': source_location.id,
            'location_dest_id': self.location_id.id,
            'handling_id': self.id,
            'picking_type_id': self.env.ref('stock.picking_type_internal').id,  # Internal Transfer
            'origin': self.name,
        }
        picking = stock_picking_obj.create(picking_vals)

        # Create stock.move for each line
        for line in self.handling_line_ids:
            if not line.product_id:
                continue
            move_vals = {
                'picking_id': picking.id,
                'product_id': line.product_id.id,
                # 'name': line.product_id.name,
                'product_uom_qty': line.quantity,
                'uom_id': line.uom_id.id,
                'location_id': source_location.id,
                'location_dest_id': self.location_id.id,
            }
            stock_move_obj.create(move_vals)

        # Confirm the transfer
        self.picking_id = picking.id
        picking.action_confirm()
        picking.action_assign()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'view_mode': 'form',
            'res_id': picking.id,
        }

    def action_view_internal_transfer(self):
        return {
            'name': _('Internal Transfer'),
            'view_mode': 'form',
            'res_model': 'stock.picking',
            'type': 'ir.actions.act_window',
            'res_id': self.picking_id.id
        }

    def action_view_adjustment(self):
        tree_view_id = self.env.ref('handling_request.view_handle_adjustment_tree').id
        return {
            'name': _('Handling Adjustment'),
            'views': [(tree_view_id, 'list')],
            'view_mode': 'list',
            'res_model': 'handle.adjustment',
            'type': 'ir.actions.act_window',
            'domain': [('id', 'in', self.adjustment_ids.ids)],
            'context':{'default_handle_id': self.id,
                       'default_location_id': self.location_id.id,
                       'default_product_ids': self.handling_line_ids.mapped('product_id').ids}
        }

