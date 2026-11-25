# -*- coding: utf-8 -*-

from datetime import datetime
from odoo.exceptions import UserError
from odoo import models, fields, api, _


class HandleAdjustment(models.Model):
    _name = 'handle.adjustment'
    _description = 'Handling Adjustment'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    handle_id = fields.Many2one('request.handling', string='Handling Request', required=True, ondelete='cascade', copy=False)
    location_id = fields.Many2one('stock.location', string='Location', required=True)
    product_id = fields.Many2one('product.product', string='Product', required=True)
    product_ids = fields.Many2many('product.product', string='Products')
    lot_id = fields.Many2one('stock.lot', string='Lot/Serial Number')
    onhand_quantity = fields.Float(string='On Hand Quantity', compute='_compute_onhand_qty')
    counted_quantity = fields.Float(string='Counted Quantity')
    difference = fields.Float(string='Difference', compute='_compute_difference', store=True, readonly=True)
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure', required=True)
    scheduled_date = fields.Date(string='Scheduled Date', default=fields.Date.today)
    user_id = fields.Many2one('res.users', string='User', default=lambda self: self.env.user)
    order_id = fields.Many2one('sale.order', string='SO')
    picking_id = fields.Many2one('stock.picking', string='SO')

    @api.depends('counted_quantity', 'onhand_quantity')
    def _compute_difference(self):
        for record in self:
            record.difference =  record.counted_quantity - record.onhand_quantity

    @api.depends('product_id', 'location_id')
    def _compute_onhand_qty(self):
        for record in self:
            if record.product_id and record.location_id:
                quants = self.env['stock.quant'].search([
                    ('product_id', '=', record.product_id.id),
                    ('location_id', '=', record.location_id.id)
                ])
                record.onhand_quantity = sum(quants.mapped('quantity'))
            else:
                record.onhand_quantity = 0.0

    @api.onchange('product_id')
    def onchange_product_id(self):
        if self.product_id:
            self.uom_id = self.product_id.uom_id.id

    def action_create_sale_order(self):
        for record in self:
            print('record >>', record)
            # Ensure difference is positive
            if record.difference == 0:
                raise UserError(_('The difference must be Less than zero to create a sale order.'))
            if record.difference <= 0:
                raise UserError(_('The difference must be greater than zero to create a sale order.'))

            # Get the partner from the user
            partner = record.user_id.partner_id
            if not partner:
                raise UserError(_('No partner associated with the current user.'))

            # Get the partner's pricelist
            pricelist = partner.property_product_pricelist
            if not pricelist:
                raise UserError(_('The partner does not have a pricelist set.'))

            # Create the sale order
            sale_order = self.env['sale.order'].create({
                'partner_id': partner.id,
                'pricelist_id': pricelist.id,
                'order_line': [(0, 0, {
                    'product_id': record.product_id.id,
                    'product_uom_qty': abs(record.difference),
                    'product_uom_id': record.product_id.uom_id.id,
                    # 'price_unit': record.product_id.lst_price,  # Adjust pricing logic as needed
                })],
            })
            record.order_id = sale_order.id

            # Optionally link the sale order to this record or notify the user
            record.message_post(body=_('Sale Order %s created successfully.' % sale_order.name))

        return True

    def action_create_sale_order_from_selected(self):
        active_ids = self.env.context.get('active_ids', [])
        records = self.env['handle.adjustment'].search([('id','in',active_ids)])
        print('records >>> ', records)
        if not active_ids:
            raise UserError(_('No records selected.'))

        # Ensure all records have the same partner (you can remove this check if not needed)
        partners = records.mapped('user_id.partner_id')
        # if len(partners) != 1:
        #     raise UserError(_('All selected records must have the same partner.'))

        partner = partners[0]
        if not partner:
            raise UserError(_('No partner is associated with the user.'))

        # Get the partner's pricelist
        pricelist = partner.property_product_pricelist
        if not pricelist:
            raise UserError(_('The partner does not have a pricelist set.'))

        # Create the sale order
        sale_order = self.env['sale.order'].create({
            'partner_id': partner.id,
            'pricelist_id': pricelist.id,
        })
        print('sale_order >> ', sale_order)
        # Add order lines for each selected record
        for record in records:
            if record.difference >= 0:
                raise UserError(
                    _('Record %s has a non-negative difference, so it cannot be included in the sale order.') % record.product_id.name)
# =======
#             if record.difference <= 0:
#                 raise UserError(
#                     _('Record %s has a non-positive difference, so it cannot be included in the sale order.') % record.product_id.name)
# >>>>>>> fb7522cba8c492411f0ecd5383e188e94b3c65a8

            sale_order.order_line.create({
                'order_id': sale_order.id,
                'product_id': record.product_id.id,
                'product_uom_qty': abs(record.difference),

                'uom_id': record.product_id.uom_id.id,
            })
            record.order_id = sale_order.id
            # record.message_post(body=_('Sale Order %s created successfully.' % sale_order.name))

    def action_create_internal_transfer_from_selected(self):
        active_ids = self.env.context.get('active_ids', [])
        records = self.env['handle.adjustment'].search([('id','in',active_ids)])
        if not active_ids:
            raise UserError(_('No records selected.'))

        # Ensure all records have the same partner (you can remove this check if not needed)
        partners = records.mapped('user_id.partner_id')
        location_id = records.mapped('location_id')[0]

        partner = partners[0]
        if not partner:
            raise UserError(_('No partner is associated with the user.'))


        # Create the sale order
        stock_picking_obj = self.env['stock.picking']
        stock_move_obj = self.env['stock.move']

        # Get the main location
        source_location = self.env['stock.location'].search([('is_main_location', '=', True)], limit=1)
        if not source_location:
            raise UserError("No main location found.")

        # Create stock.picking
        picking_vals = {
            'location_id': location_id.id,
            'location_dest_id': source_location.id,
            'handling_id': records[0].handle_id.id,
            'picking_type_id': self.env.ref('stock.picking_type_internal').id,  # Internal Transfer
            'origin': records[0].handle_id.name,
        }
        picking = stock_picking_obj.create(picking_vals)

        # Create stock.move for each line
        for line in records:
            if not line.product_id:
                continue
            move_vals = {
                'picking_id': picking.id,
                'product_id': line.product_id.id,
                #'name': line.product_id.name,
                'product_uom_qty': line.counted_quantity,
                'uom_id': line.uom_id.id,
                'location_id': location_id.id,
                'location_dest_id': source_location.id,
            }
            stock_move_obj.create(move_vals)

        # Confirm the transfer
        records[0].handle_id.picking_id = picking.id
        picking.action_confirm()
        picking.action_assign()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'view_mode': 'form',
            'res_id': picking.id,
        }
    def action_create_internal_transfer(self):
        for rec in self:

            # Ensure all records have the same partner (you can remove this check if not needed)
            partner = rec.user_id.partner_id

            location_id = rec.location_id

            if not partner:
                raise UserError(_('No partner is associated with the user.'))


            # Create the sale order
            stock_picking_obj = self.env['stock.picking']
            stock_move_obj = self.env['stock.move']

            # Get the main location
            source_location = self.env['stock.location'].search([('is_main_location', '=', True)], limit=1)
            if not source_location:
                raise UserError("No main location found.")

            # Create stock.picking
            picking_vals = {
                'partner_id':partner.id,
                'location_id': location_id.id,
                'location_dest_id': source_location.id,
                'handling_id': rec.handle_id.id,
                'picking_type_id': self.env.ref('stock.picking_type_internal').id,  # Internal Transfer
                'origin': rec.handle_id.name,
            }
            picking = stock_picking_obj.create(picking_vals)

            # Create stock.move for each line
            move_vals = {
                'picking_id': picking.id,
                'product_id': rec.product_id.id,
                #'name': rec.product_id.name,
                'product_uom_qty': rec.counted_quantity,
                'uom_id': rec.uom_id.id,
                'location_id': location_id.id,
                'location_dest_id': source_location.id,
            }
            stock_move_obj.create(move_vals)

            # Confirm the transfer
            rec.picking_id = picking.id
            picking.action_confirm()
            picking.action_assign()

