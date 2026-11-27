from odoo import fields, models, api, _


class InheritConf(models.TransientModel):
    _inherit = 'res.config.settings'

    account_id = fields.Many2one("account.account", config_parameter='inherit_purchase.account_id')
    journal_id = fields.Many2one("account.journal", config_parameter='inherit_purchase.journal_id')
