# -*- coding: utf-8 -*-
from datetime import datetime
from odoo import models, fields, api


class StockLocation(models.Model):
    _inherit = 'stock.location'

    is_main_location = fields.Boolean(string="Main Location For Handling?")


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    handling_id = fields.Many2one(comodel_name="stock.picking", copy=False)
