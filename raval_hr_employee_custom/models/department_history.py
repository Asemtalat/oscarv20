from odoo import api, fields, models


class DepartmentHistory(models.Model):
    _name = 'hr.department.history'
    _description = 'HR Department History'

    employee_id = fields.Many2one('hr.employee', required=1)
    from_department_id = fields.Many2one('hr.department', required=1)
    to_department_id = fields.Many2one('hr.department', required=1)
    date = fields.Datetime(required=1)
