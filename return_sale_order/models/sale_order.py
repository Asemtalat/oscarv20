from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.addons.sale.models.sale_order import SaleOrder
from openpyxl.styles.builtins import total


class SaleOrderInherit(models.Model):
    _inherit = 'sale.order'

    return_order = fields.Boolean(string='Return Order', default=False)
    entry_count = fields.Integer(string='Return Entry Count', compute='_compute_return_entry_count')
    return_entry_ids = fields.Many2many('account.move', 'sale_order_return_move_rel', 'sale_return_id', 'return_move_id', copy=False)

    # picking_count = fields.Integer(string="Picking Count", compute='_compute_picking_count')
    #
    # def _compute_picking_count(self):
    #     for order in self:
    #         order.picking_count = len(order.picking_ids)

    def action_journal_entry_return(self):
        # return_journal_id = self.env['ir.config_parameter'].sudo().get_param('return_sale_order.return_journal_id')
        # return_debit_account_id = float(self.env['ir.config_parameter'].sudo().get_param('return_sale_order.return_debit_account_id', 0.0))
        # return_credit_account_id = float(self.env['ir.config_parameter'].sudo().get_param('return_sale_order.return_credit_account_id', 0.0))
        values = self.env['res.config.settings'].sudo().default_get(['return_journal_id', 'return_debit_account_id', 'return_credit_account_id'])
        return_journal_id = values.get('return_journal_id')
        return_debit_account_id = values.get('return_debit_account_id')
        return_credit_account_id = values.get('return_credit_account_id')

        amount_total = self.amount_total

        if not return_journal_id:
            raise UserError("Return Journal is not configured in settings.")
        if not return_debit_account_id:
            raise UserError("Return Debit Account is not configured in settings.")
        if not return_credit_account_id:
            raise UserError("Return Credit Account is not configured in settings.")

        account_move_obj = self.env['account.move']
        for rec in self:
            if not rec.order_line:
                raise UserError("No Order lines to process for this Invoice.")

            if not rec.partner_id.property_account_receivable_id or not rec.partner_id.property_account_payable_id:
                raise UserError("The partner must have receivable and payable accounts configured.")

            line_ids = [
                (0, 0, {
                    'account_id': int(return_credit_account_id),
                    'credit': amount_total,
                    'debit': 0.0,
                }),
                (0, 0, {
                    'account_id': int(return_debit_account_id),
                    'debit': amount_total,
                    'credit': 0.0,
                })]

            move_id = account_move_obj.create({
                'partner_id': rec.partner_id.id,
                'move_type': 'entry',
                'journal_id': int(return_journal_id),
                'line_ids': line_ids,
                'invoice_origin': rec.name,
                'return_order_id':rec.id
            })
            self.return_entry_ids = [(4, move_id.id)]

    @api.depends('return_entry_ids')
    def _compute_return_entry_count(self):
        for order in self:
            order.entry_count = 0
            if order.return_entry_ids:
                count = len(order.return_entry_ids)
                order.entry_count = count

    def action_view_return_entry(self):
        entries = self.return_entry_ids
        if not entries:
            raise UserError("No related Return Entries Found for this Return Order.")
        return {
            'type': 'ir.actions.act_window',
            'name': 'Return Entries',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', entries.ids)],
            'target': 'current',
        }

    # def action_view_pickings(self):
    #     pickings = self.mapped('picking_ids')
    #     action = self.env["ir.actions.actions"]._for_xml_id("stock.action_picking_tree_all")
    #     if len(pickings) > 1:
    #         action['domain'] = [('id', 'in', pickings.ids)]
    #     elif pickings:
    #         action['views'] = [(self.env.ref('stock.view_picking_form').id, 'form')]
    #         action['res_id'] = pickings.id
    #     return action

    # def action_create_return_picking(self):
    #     for order in self:
    #         delivery_pickings = order.picking_ids.filtered(
    #             lambda p: p.picking_type_id.code == 'outgoing' and p.state == 'done')
    #         if not delivery_pickings:
    #             raise UserError("No completed delivery order found to process the return.")
    #
    #         for picking in delivery_pickings:
    #             return_wizard = self.env['stock.return.picking'].with_context(active_id=picking.id,
    #                                                                           active_model='stock.picking').create({
    #                 'picking_id': picking.id,
    #             })
    #             return_wizard.create_returns()

    def action_confirm(self):
        res = super(SaleOrderInherit, self).action_confirm()
        for rec in self:
            if rec.return_order:
                rec.action_journal_entry_return()
        return res

    def _prepare_invoice(self):
        values = super()._prepare_invoice()
        if self.return_order:
            values.update({
                'move_type': 'out_refund'
            })
        return values

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _("New")) == _("New") and not vals.get('return_order',False):
                seq_date = fields.Datetime.context_timestamp(
                    self, fields.Datetime.to_datetime(vals['date_order'])
                ) if 'date_order' in vals else None
                vals['name'] = self.env['ir.sequence'].with_company(vals.get('company_id')).next_by_code(
                    'sale.order', sequence_date=seq_date) or _("New")
            elif vals.get('name', _("New")) == _("New") and vals.get('return_order',False):
                seq_date = fields.Datetime.context_timestamp(
                    self, fields.Datetime.to_datetime(vals['date_order'])
                ) if 'date_order' in vals else None
                vals['name'] = self.env['ir.sequence'].with_company(vals.get('company_id')).next_by_code(
                    'sale.order.return', sequence_date=seq_date) or _("New")

        return super(SaleOrder, self).create(vals_list)


class AccountMoveInherit(models.Model):
    _inherit = 'account.move'

    return_order_id = fields.Many2one(
        comodel_name='sale.order',
        string='Return Order',
        copy=False)


class SaleReport(models.Model):
    _inherit = 'sale.report'

    return_order = fields.Boolean(string="Return Order", readonly=True)

    def _select_additional_fields(self):
        res = super()._select_additional_fields()
        res['return_order'] = 's.return_order'
        return res
