from odoo import api, fields, models

class InsuranceGrades(models.Model):
    _name = 'insurance.grades'
    _description = 'InsuranceGrades'

    name = fields.Char(required=True)
