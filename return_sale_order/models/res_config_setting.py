from odoo import models, fields, api

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    return_journal_id = fields.Many2one('account.journal', string='Return Journal', config_parameter='return_sale_order.return_journal_id', readonly=False)
    return_debit_account_id = fields.Many2one("account.account", string='Return Debit Account', config_parameter='return_sale_order.return_debit_account_id', readonly=False)
    return_credit_account_id = fields.Many2one("account.account", string='Return Credit Account', config_parameter='return_sale_order.return_credit_account_id', readonly=False)