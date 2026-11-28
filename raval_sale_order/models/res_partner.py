from odoo import models, fields, api


class ResPartner(models.Model):
    _inherit = 'res.partner'

    allow_discount = fields.Boolean(string='Allow Discount', default=False)
    discount_rate = fields.Float(string='Discount (%)', default=0.0)
