from odoo import fields, models, api, _


class PaymentWizard(models.TransientModel):
    _name = 'payment.wizard'
    _description = 'Purchase Down Payment Wizard'

    description = fields.Char(string='Description')
    price = fields.Monetary(string='Price', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', string='Currency', required=True,
                                  default=lambda self: self.env.company.currency_id)
    percentage_price = fields.Float(string='Price of Percentage')
    account_id = fields.Many2one('account.account', string='Account', domain=[('account_type', '=', 'asset_cash')])
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
        journal_id = self.env['ir.config_parameter'].sudo().get_param('inherit_purchase.journal_id')
        account_id = int(self.env['ir.config_parameter'].sudo().get_param('inherit_purchase.account_id'))
        move = self.env['account.move'].create({
            'journal_id': int(journal_id),
            'date': fields.Date.today(),
            'line_ids': [
                (0, 0, {
                    'partner_id': self.purchase_id.partner_id.id,
                    'account_id': int(account_id),
                    'name': self.description,
                    'debit': 100.0,
                    'credit': 0.0,
                }),
                (0, 0, {
                    'partner_id': self.purchase_id.partner_id.id,
                    'account_id': int(account_id),
                    'name': self.description,
                    'debit': 0.0,
                    'credit': 100.0,
                })
            ]
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Journal Entry'),
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': move.id,
            'target': 'current',
        }
