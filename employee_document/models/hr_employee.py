from odoo import fields, models, api, _


class HrEmployee(models.Model):
    _inherit = 'hr.employee'
    documents_count = fields.Integer(string='Invoice Count', compute='_compute_documents_count')

    def _compute_documents_count(self):
        for order in self:
            order.documents_count = len(self.env['hr.document.lines'].search([('employee_id', '=', order.id)]))

    def action_view_documents(self):
        employee = self.env['hr.document.lines'].search([('employee_id', '=', self.id)])
        print(employee)
        return {
            'type': 'ir.actions.act_window',
            'name': 'Documents',
            'res_model': 'hr.document.lines',
            'view_mode': 'list,form',
            'domain': [('id', 'in', employee.ids)],
            'context': dict(self.env.context),
            'target': 'current',
        }
