# -*- coding: utf-8 -*-

from odoo import models, fields, api


class Contract(models.Model):
    _inherit = 'hr.version'

    # Add new fields to contract model
    basic = fields.Float()
    car_allowance = fields.Float()
    mobile_allowance = fields.Float()
    transportation_allowance = fields.Float()
    other_allowance = fields.Float()
    basic_insurance_allowance = fields.Float()

    social_insurance_line = fields.One2many(comodel_name='social.insurance.line', inverse_name='contract_id')
    medical_insurance_line = fields.One2many(comodel_name='medical.insurance.line', inverse_name='contract_id')
