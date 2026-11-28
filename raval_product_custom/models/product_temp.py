# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ProductTemp(models.Model):
    _inherit = 'product.template'

    country_id = fields.Many2one('res.country')
