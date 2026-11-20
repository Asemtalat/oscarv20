# -*- coding: utf-8 -*-
# Copyright (C) NexGen Solutions
from odoo import api, fields, models

class AccessManagementTag(models.Model):
    _name = 'access.management.tag'
    _description = 'Access Management Tag'

    name = fields.Char(string='Name', required=True, translate=True)
    color = fields.Integer(string='Color')
