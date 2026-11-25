# -*- coding: utf-8 -*-

from datetime import datetime
from odoo import models, fields, api, _



class RequestSales(models.Model):
    _inherit = 'request.sales'

    handle_id = fields.Many2one(comodel_name="request.handling")

    def action_create_handling_request(self):
        handling_request = self.env['request.handling'].create({
            'user_id': self.user_id.id,
            'scheduled_date': self.scheduled_date,
            'location_id': self.location_id.id,
            # self.user_id.allowed_locations_ids[0].id if self.user_id.allowed_locations_ids else

            'request_sales_id': self.id,
            'handling_line_ids': [(0, 0, {
                'product_id': line.product_id.id,
                'uom_id': line.product_id.uom_id.id,
                'quantity': line.done_qty,
                'request_sales_line_id': line.id,
            }) for line in self.request_lines],
        })
        self.handle_id = handling_request.id

        for line in handling_request.handling_line_ids:
            self.env['handle.adjustment'].create({
                'handle_id': handling_request.id,
                'location_id': self.location_id.id,
                'product_id': line.product_id.id,
                'uom_id': line.product_id.uom_id.id,
                'scheduled_date': self.scheduled_date,
                'user_id': self.user_id.id,
            })

        return {
            'name': 'Handling Request',
            'type': 'ir.actions.act_window',
            'res_model': 'request.handling',
            'res_id': handling_request.id,
            'view_mode': 'form',
        }

    def action_view_handling_request(self):
        return {
            'name': _('Handling Request'),
            'view_mode': 'form',
            'res_model': 'request.handling',
            'type': 'ir.actions.act_window',
            'res_id': self.handle_id.id
        }
