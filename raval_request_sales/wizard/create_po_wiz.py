from odoo import api, fields, models

class CreatePOWizard(models.TransientModel):
    _name = 'create.po.wizard'
    _description = 'CreatePOWizard'

    selected_line_ids = fields.Many2many('request.sales.lines', string="Selected Lines")

    def action_create_po(self):
        self.selected_line_ids.action_create_po()
        return {'type': 'ir.actions.act_window_close'}
