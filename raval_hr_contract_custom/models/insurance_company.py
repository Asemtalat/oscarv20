from odoo import api, fields, models

class InsuranceCompany(models.Model):
    _name = 'insurance.company'
    _description = 'Insurance Company'

    name = fields.Char(required=True)
