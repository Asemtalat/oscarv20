# -*- coding: utf-8 -*-
from datetime import datetime
from collections import defaultdict

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class RequestSalesLines(models.Model):
    _name = 'request.sales.lines'
    _description = 'Request Sales Lines'

    request_id = fields.Many2one(comodel_name='request.sales')
    product_id = fields.Many2one(comodel_name='product.product', required=True)
    categ_id = fields.Many2one(related='product_id.categ_id', store=1)
    quantity = fields.Float(default=1)
    uom_id = fields.Many2one(comodel_name='uom.uom', string='UoM', required=True)
    scheduled_date = fields.Date(related='request_id.scheduled_date')
    available_qty = fields.Float(groups='raval_request_sales.available_diff_group')
    diff_qty = fields.Float(string='Difference Qty', compute='_compute_difference_qty', store=True,
                            groups='raval_request_sales.available_diff_group')
    done_qty = fields.Float(groups='raval_request_sales.group_done_qty')
    user_id = fields.Many2one(related='request_id.user_id', store=1)
    purchase_id = fields.Many2one(comodel_name='purchase.order')

    def action_open_lines(self):
        if self.purchase_id:
            raise ValidationError(_('You already have purchase!'))
        return {
            'name': 'Request Sales Lines',
            'view_mode': 'form',
            'res_model': 'create.po.wizard',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'context': {
                'default_selected_line_ids': [(6, 0, self.ids)]
            }
        }

    @api.onchange('quantity')
    def _set_done_quantity(self):
        self.done_qty = self.quantity

    @api.onchange('product_id')
    def onchange_product_id(self):
        if self.product_id:
            self.uom_id = self.product_id.uom_id.id
            available_qty = self.env['stock.quant'].search([
                ('product_id', '=', self.product_id.id),
                ('on_hand', '=', True),
                ('location_id.usage', '=', 'internal'),
            ]).mapped('available_quantity')
            self.available_qty = sum(available_qty)

    @api.depends('done_qty', 'available_qty')
    def _compute_difference_qty(self):
        for line in self:
            line.diff_qty = line.available_qty - line.done_qty

    def action_create_po(self):
        if not self:
            raise ValidationError(_("No lines selected."))

        po_obj = self.env['purchase.order']

        grouped_qty = {}
        for line in self:
            product = line.product_id
            key = product.id
            qty_in_product_uom = line.uom_id._compute_quantity(line.quantity or 0.0, product.uom_id,
                                                               rounding_method='HALF-UP')
            if key in grouped_qty:
                grouped_qty[key]['qty'] += qty_in_product_uom
            else:
                grouped_qty[key] = {'product': product, 'qty': qty_in_product_uom}

        order_lines = []
        for item in grouped_qty.values():
            if item['qty'] <= 0:
                continue
            product = item['product']
            order_lines.append((0, 0, {
                'name': product.display_name,
                'product_id': product.id,
                'uom_id': product.uom_id.id,
                'product_qty': item['qty'],
                'price_unit': product.product_tmpl_id.list_price,
                'date_planned': fields.Datetime.now(),
            }))
        print("order_lines:", order_lines)
        if not order_lines:
            raise ValidationError(_("No quantities to purchase."))

        po = po_obj.create({'order_line': order_lines})
        self.write({'purchase_id': po.id})

        return {
            'name': _('Purchase Order'),
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'view_mode': 'form',
            'view_id': self.env.ref('purchase.purchase_order_form').id,
            'target': 'current',
            'res_id': po.id,
        }

    def action_open_purchase(self):
        return {
            'name': 'Purchase Order',
            'view_mode': 'form',
            'res_model': 'purchase.order',
            'type': 'ir.actions.act_window',
            'target': 'current',
            'res_id': self.purchase_id.id,
        }


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    partner_id = fields.Many2one('res.partner', string='Vendor', required=False, index=True, change_default=True,
                                 tracking=True, check_company=True,
                                 help="You can find a vendor by its Name, TIN, Email or Internal Reference.")
