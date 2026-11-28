from odoo import fields, models


class JobPositionHistory(models.Model):
    _name = 'hr.job.history'
    _description = 'JobPositionHistory'

    employee_id = fields.Many2one('hr.employee', required=1)
    from_job_id = fields.Many2one('hr.job', required=1)
    to_job_id = fields.Many2one('hr.job', required=1)
    date = fields.Datetime(required=1)
