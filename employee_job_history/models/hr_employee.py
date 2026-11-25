from odoo import fields, models, api, _


class HrEmployee(models.Model):
    _inherit = 'hr.employee'
    job_history_ids = fields.One2many('hr.job.lines', 'employee_id', string="Job History")
    @api.constrains('job_id')
    def _create_job_history(self):
        for rec in self:
            if rec.job_id:
                job_lines = self.env['hr.job.lines'].create({
                    'employee_id': rec.id,
                    'department_id': rec.department_id.id,
                    'job_id': rec.job_id.id,
                    'promotion_date': fields.Date.today(),
                    'user_id': self.env.user.id
                })
