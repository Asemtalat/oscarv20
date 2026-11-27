# -*- coding: utf-8 -*-

from odoo import models, fields, api


class Partner(models.Model):
    _inherit = 'res.partner'

    customer_type = fields.Selection([
        ('cash', 'Cash'),
        ('in-adv', 'In-Advance Payment'),
    ])

    tax_no = fields.Char(string='Tax #')
    check_trust_no = fields.Char(string='Check/Trust Receipt #')
    check_trust_date = fields.Date(string='Check/Trust Receipt Date')
    check_trust_amount = fields.Float(string='Check/Trust Receipt Amount')
    warranty_file = fields.Binary(string='Warranty')
