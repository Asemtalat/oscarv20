from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    backorder_mrp_id = fields.Many2one(comodel_name='mrp.production')
