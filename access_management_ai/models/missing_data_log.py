# -*- coding: utf-8 -*-
# Copyright (C) NexGen Solutions
from odoo import api, fields, models

class AccessMissingDataLog(models.Model):
    _name = 'access.missing.data.log'
    _description = 'Access Management Missing Data Log'
    _order = 'create_date desc'

    name = fields.Char(string='Missing Record/Field Name')
    model_name = fields.Char(string='Model Name')
    field_name = fields.Char(string='Field Name')
    missing_type = fields.Selection([
        ('model', 'Model'),
        ('field', 'Field'),
        ('element', 'Element'),
    ], string='Missing Type')
    message = fields.Text(string='Message')
    import_date = fields.Datetime(string='Import Date', default=fields.Datetime.now)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
