# -*- coding: utf-8 -*-

from datetime import datetime
from odoo import models, fields, api


class RequestHandlingLine(models.Model):
    _name = 'request.handling.line'
    _description = 'Handling Request Line'

    handling_id = fields.Many2one('request.handling', string='Handling Request', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Product')
    quantity = fields.Float(string='Quantity', default=1.0)
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure')
    request_sales_line_id = fields.Many2one(comodel_name='request.sales.lines')

    @api.onchange('product_id')
    def onchange_product_id(self):
        if self.product_id:
            self.uom_id = self.product_id.uom_id.id

