from odoo import fields, models, api, _


class HrDocument(models.Model):
    _name = 'hr.document'

    name = fields.Char("Name", required=True)
    employee_id = fields.Many2one('hr.employee', string="Employee")


class HrDocumentLines(models.Model):
    _name = 'hr.document.lines'
    _rec_name = 'employee_id'

    document_id = fields.Many2one('hr.document', string="Document")
    employee_id = fields.Many2one('hr.employee', string="Employee")
    document = fields.Binary("Attachment")
    description = fields.Text("Description")
    date_expired = fields.Date("Date Expired")
    state = fields.Selection([('draft', 'Draft'), ('submitted', 'Submitted'), ('issued', 'Issued'), ('expired', 'Expired')], default='draft')

    def action_done(self):
        self.write({'state': 'done'})

    def action_draft(self):
        self.write({'state': 'draft'})
