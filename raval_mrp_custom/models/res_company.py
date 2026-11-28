from odoo import api, fields, models

class Company(models.Model):
    _inherit = 'res.company'

    mrp_debit_account_id = fields.Many2one('account.account')
    mrp_credit_account_id = fields.Many2one('account.account')
    mrp_journal_id = fields.Many2one('account.journal')

