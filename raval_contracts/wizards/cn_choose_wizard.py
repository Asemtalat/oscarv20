from odoo import api, fields, models
from odoo.exceptions import ValidationError


class CNoteChooseWizard(models.TransientModel):
    _name = 'cn.choose.wizard'
    _inherit = 'rav.contracts'
    _description = 'CreditNoteWizard'

    partner_id = fields.Many2one(comodel_name='res.partner', required=False)

    def create_credit_note(self):
        active_id = self._context.get('active_id')
        contract = self.env['rav.contracts'].browse(active_id)
        fields_data = self._get_bool_fields_data()
        bool_data = fields_data['bool_data']

        selected_fields = list(filter(lambda x: getattr(self, x), bool_data))

        if not selected_fields:
            raise ValidationError('No selected fields found!')
        return contract.create_credit_note(bool_data=selected_fields)

