from dateutil.relativedelta import relativedelta

from odoo import api, fields, models

class MedicalInsuranceLine(models.Model):
    _name = 'medical.insurance.line'
    _description = 'MedicalInsuranceLine'

    contract_id = fields.Many2one('hr.version')

    employee_id = fields.Many2one(related='contract_id.employee_id')
    start_date = fields.Date(default=fields.Date.today())
    end_date = fields.Date(default=fields.Date.today() + relativedelta(months=1))
    insurance_number = fields.Char('Medical Insurance Number')
    company_id = fields.Many2one('insurance.company')
