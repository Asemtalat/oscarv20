from odoo import api, fields, models


class ConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    mrp_debit_account_id = fields.Many2one(related='company_id.mrp_debit_account_id', string='Debit Account', readonly=False)
    mrp_credit_account_id = fields.Many2one(related='company_id.mrp_credit_account_id', string='Credit Account', readonly=False)
    mrp_journal_id = fields.Many2one(related='company_id.mrp_journal_id', string='Journal', readonly=False)
