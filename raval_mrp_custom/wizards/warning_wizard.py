from odoo import api, fields, models

class WarningWizard(models.TransientModel):
    _name = 'quant.wiz.warning'
    _description = 'WarningWizard'

    name = fields.Html()

    def action_produce_warning(self):
        active_ids = self.env.context.get('active_ids')
        return self.env['mrp.production'].browse(active_ids).button_mark_done()
