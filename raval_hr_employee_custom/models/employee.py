from odoo import fields, models


class HREmployee(models.Model):
    _inherit = 'hr.employee'

    job_history_lines = fields.One2many(comodel_name='hr.job.history', inverse_name='employee_id')
    department_history_lines = fields.One2many(comodel_name='hr.department.history', inverse_name='employee_id')

    def write(self, vals):
        job_history_vals = []
        department_history_vals = []
        now = fields.Datetime.now()
        # write() may be called on several employees at once
        for employee in self:
            new_job_id = vals.get('job_id') if 'job_id' in vals else False
            if new_job_id and new_job_id != employee.job_id.id:
                job_history_vals.append({
                    'employee_id': employee.id,
                    'from_job_id': employee.job_id.id,
                    'to_job_id': new_job_id,
                    'date': now,
                })
            new_department_id = vals.get('department_id') if 'department_id' in vals else False
            if new_department_id and new_department_id != employee.department_id.id:
                department_history_vals.append({
                    'employee_id': employee.id,
                    'from_department_id': employee.department_id.id,
                    'to_department_id': new_department_id,
                    'date': now,
                })

        res = super().write(vals)
        if job_history_vals:
            self.env['hr.job.history'].create(job_history_vals)
        if department_history_vals:
            self.env['hr.department.history'].create(department_history_vals)
        return res
