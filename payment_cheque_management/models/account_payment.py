from odoo import _, api, fields, models
from odoo.exceptions import UserError

CHEQUE_METHOD_KEYWORD = 'شيك'


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    is_cheque = fields.Boolean(string='شيك', tracking=True)
    cheque_deposit_account_id = fields.Many2one(
        'account.account',
        string='حساب الإيداع',
        tracking=True,
        copy=False,
        domain="[('account_type', 'in', ('asset_cash', 'asset_current'))]",
    )
    cheque_deposit_move_id = fields.Many2one(
        'account.move',
        string='قيد الإيداع',
        readonly=True,
        copy=False,
    )

    # ------------------------------------------------------------------
    # Onchange: tick "Cheque" -> select the cheque payment method
    # ------------------------------------------------------------------
    @api.onchange('is_cheque')
    def _onchange_is_cheque(self):
        for rec in self:
            if not rec.is_cheque:
                continue
            line = rec.available_payment_method_line_ids.filtered(
                lambda l: CHEQUE_METHOD_KEYWORD in (l.name or '')
            )[:1]
            if line:
                rec.payment_method_line_id = line

    # ------------------------------------------------------------------
    # Deposit
    # ------------------------------------------------------------------
    def action_cheque_deposit(self):
        for rec in self:
            if not rec.is_cheque or rec.state != 'paid':
                raise UserError(_("الإيداع متاح بس للشيكات في حالة مدفوع."))
            if not rec.cheque_deposit_account_id:
                raise UserError(_("اختار حساب الإيداع الأول."))

            out_acc = rec.outstanding_account_id
            out_lines = rec.move_id.line_ids.filtered(
                lambda l: l.account_id == out_acc and not l.reconciled
            )
            if not out_lines:
                raise UserError(_("مفيش رصيد مفتوح على حساب %s للتسوية.", out_acc.display_name))

            balance = sum(out_lines.mapped('balance'))
            amount_currency = sum(out_lines.mapped('amount_currency'))
            currency = out_lines[0].currency_id
            dep_acc = rec.cheque_deposit_account_id

            Journal = self.env['account.journal']
            journal = Journal.search([
                ('type', '=', 'bank'),
                ('default_account_id', '=', dep_acc.id),
                ('company_id', '=', rec.company_id.id),
            ], limit=1) or Journal.search([
                ('type', '=', 'general'),
                ('company_id', '=', rec.company_id.id),
            ], limit=1)
            if not journal:
                raise UserError(_("مفيش دفتر يومية مناسب لقيد الإيداع."))

            label = _("إيداع شيك %s", rec.name or '')
            common = {
                'name': label,
                'partner_id': rec.partner_id.id,
                'currency_id': currency.id,
            }
            move = self.env['account.move'].create({
                'move_type': 'entry',
                'journal_id': journal.id,
                'date': fields.Date.context_today(rec),
                'ref': label,
                'line_ids': [
                    fields.Command.create({
                        **common,
                        'account_id': dep_acc.id,
                        'balance': balance,
                        'amount_currency': amount_currency,
                    }),
                    fields.Command.create({
                        **common,
                        'account_id': out_acc.id,
                        'balance': -balance,
                        'amount_currency': -amount_currency,
                    }),
                ],
            })
            move.action_post()
            (out_lines + move.line_ids.filtered(lambda l: l.account_id == out_acc)).reconcile()

            rec.cheque_deposit_move_id = move
            rec.invalidate_recordset()
            if rec.state != 'reconciled':
                rec.state = 'reconciled'
            rec.message_post(body=_(
                "تم إيداع الشيك على حساب %(account)s - قيد %(move)s",
                account=dep_acc.display_name, move=move.name,
            ))
        return True

    # ------------------------------------------------------------------
    # Bounce
    # ------------------------------------------------------------------
    def action_cheque_bounce(self):
        for rec in self:
            if not rec.is_cheque or rec.state != 'paid':
                raise UserError(_("الارتداد متاح بس للشيكات في حالة مدفوع."))
            move = rec.move_id
            if move:
                move.line_ids.remove_move_reconcile()
                if move.state == 'posted':
                    move.button_draft()
                rec.move_id = False
                move.with_context(force_delete=True).unlink()
            rec.state = 'rejected'
            rec.message_post(body=_("تم تحويل الشيك إلى مرتد وحذف القيد."))
        return True

    # ------------------------------------------------------------------
    # Reset to draft also deletes the deposit entry
    # ------------------------------------------------------------------
    def _cheque_remove_deposit_move(self):
        for rec in self.filtered('cheque_deposit_move_id'):
            dep = rec.cheque_deposit_move_id
            dep_name = dep.name
            dep.line_ids.remove_move_reconcile()
            if dep.state == 'posted':
                dep.button_draft()
            rec.cheque_deposit_move_id = False
            dep.with_context(force_delete=True).unlink()
            rec.message_post(body=_("تم مسح قيد الإيداع %s", dep_name))

    def action_draft(self):
        self._cheque_remove_deposit_move()
        return super().action_draft()
