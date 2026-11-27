from odoo import api, fields, models

class AccountTax(models.Model):
    _inherit = 'account.tax'


    @api.model
    def _prepare_base_line_for_taxes_computation(self, record, **kwargs):
        res = super(AccountTax, self)._prepare_base_line_for_taxes_computation(record, **kwargs)
        def load(field, fallback):
            return self._get_base_line_field_value_from_record(record, field, kwargs, fallback)
        if record and 'contract_disc' in record._fields:
            res['discount'] = load('discount', 0.0) + (load('contract_disc', 0.0) * 100)
        return res
