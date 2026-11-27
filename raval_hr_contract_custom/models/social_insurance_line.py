from dateutil.relativedelta import relativedelta

from odoo import api, fields, models

class SocialInsuranceLine(models.Model):
    _name = 'social.insurance.line'
    _description = 'SocialInsuranceLine'

    contract_id = fields.Many2one('hr.version')

    employee_id = fields.Many2one(related='contract_id.employee_id')
    start_date = fields.Date(default=fields.Date.today())
    end_date = fields.Date(default=fields.Date.today() + relativedelta(months=1))
    insurance_number = fields.Char('Social Insurance Number')
    state = fields.Selection(selection=[
        ('yes', 'Yes'),
        ('no', 'No'),
    ], default='yes')
    grade_id = fields.Many2one('insurance.grades')

