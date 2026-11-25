from odoo import api, fields, models

class ResUsers(models.Model):
    _inherit = 'res.users'

    allowed_locations_ids = fields.Many2many(comodel_name='stock.location')
