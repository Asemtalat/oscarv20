from odoo import fields, models, api, _


class HrDocumentLines(models.Model):
    _name = 'hr.job.lines'
    _rec_name = 'employee_id'

    employee_id = fields.Many2one('hr.employee', string="Employee")
    department_id = fields.Many2one('hr.department', string="Department")
    job_id = fields.Many2one('hr.job', string="Job")
    promotion_date = fields.Date(string="Promotion Date")
    user_id = fields.Many2one('res.users', string="User")
