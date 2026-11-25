# -*- coding: utf-8 -*-
"""
Model to record merchant visit logs from the mobile application. Each visit
record links a delivery user to a merchant (customer) and stores the
timestamp and optional notes. The records can be queried through the API
to retrieve the visit history for a specific user and date.
"""

from odoo import fields, models


class MerchantVisit(models.Model):
    _name = 'merchant.visit'
    _description = 'Merchant Visit'

    user_id = fields.Many2one('res.users', required=True, string='Delivery User')
    partner_id = fields.Many2one('res.partner', required=True, string='Merchant')
    visit_datetime = fields.Datetime(required=True, default=fields.Datetime.now, string='Visit Time')
    notes = fields.Text(string='Notes')