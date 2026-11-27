from odoo import fields, models, api, _
from odoo.exceptions import UserError


class PaymentWizard(models.TransientModel):
    _name = 'payment.wizard'

    description = fields.Char(string='Description')
    price = fields.Monetary(string='Price', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', string='Currency', required=True,
                                  default=lambda self: self.env.company.currency_id)
    percentage_price = fields.Float(string='Price of Percentage')
    account_id = fields.Many2one('account.account', string='Account', domain=[('account_type', '=', 'asset_cash')], required=True)
    payment_method = fields.Selection([('percentage', 'Percentage'), ('fixed_amount', 'Fixed Amount')],
                                      default='fixed_amount')
    purchase_id = fields.Many2one('purchase.order', string='Purchase Order')

    total_order_amount = fields.Monetary(string="Total Order Amount", currency_field='currency_id',
                                         compute='_compute_total_order_amount')

    @api.depends('purchase_id')
    def _compute_total_order_amount(self):
        for wizard in self:
            wizard.total_order_amount = wizard.purchase_id.amount_total if wizard.purchase_id else 0.0

    def action_create_journal(self):
        # ICP = self.env['ir.config_parameter'].sudo()
        # journal_id = int(ICP._get_param('inherit_purchase.journal_id') or 0)
        # account_id = int(ICP._get_param('inherit_purchase.account_id') or 0)
        values = self.env['res.config.settings'].sudo().default_get(['journal_id', 'account_id'])
        journal_id = values.get('journal_id')
        account_id = values.get('account_id')
        if not (journal_id and account_id):
            raise UserError(_("Journal and account must be set in configuration."))

        if self.payment_method == 'fixed_amount':
            amount = self.price
        else:
            amount = self.percentage_price * self.total_order_amount

        move = self.env['account.move'].create({
            'journal_id': journal_id,
            'date': fields.Date.today(),
            'line_ids': [
                (0, 0, {
                    'partner_id': self.purchase_id.partner_id.id,
                    'account_id': account_id,
                    'debit': amount,
                    'credit': 0.0,
                }),
                (0, 0, {
                    'account_id': self.account_id.id,
                    'name': self.description,
                    'debit': 0.0,
                    'credit': amount,
                }),
            ],
        })
        self.purchase_id.downpayment_move_ids = [(4, move.id)]
        return {
            'type': 'ir.actions.act_window',
            'name': _('Journal Entry'),
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': move.id,
            'target': 'current',
        }