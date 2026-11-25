# -*- coding: utf-8 -*-
from odoo import models, fields

class ApiRule(models.Model):
    _name = 'api.rules'
    _description = 'API Rule'

    name = fields.Char(string='Rule Name', required=True)
    operations = fields.Text(
        string='Operations (JSON)',
        help='Stores JSON representation or comma-separated list of allowed operations assigned by mobile app'
    )
