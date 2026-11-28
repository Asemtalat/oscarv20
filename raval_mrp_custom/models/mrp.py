# -*- coding: utf-8 -*-
from markupsafe import Markup

from odoo import models, fields, api, _
from odoo.exceptions import UserError, RedirectWarning


class MRP(models.Model):
    _inherit = 'mrp.production'

    acc_moves_ids = fields.One2many(comodel_name='account.move', inverse_name='backorder_mrp_id')
    entries_counts = fields.Integer(compute='_compute_entries_count')

    def action_produce_warning(self):
        quantity_changed = self.move_raw_ids.filtered(lambda x: x.product_id and x.change_qty > 0).product_id
        if quantity_changed:
            products = Markup('<br/>').join(quantity_changed.mapped('name'))
            return {
                'type': 'ir.actions.act_window',
                'name': 'Warning',
                'res_model': 'quant.wiz.warning',
                'view_mode': 'form',
                'context': {
                    'active_ids': self.ids,
                    'default_name': Markup('These products are changed!<br/>%s') % products,
                },
                'target': 'new',
            }
        return self.button_mark_done()

    @api.depends('acc_moves_ids')
    def _compute_entries_count(self):
        for rec in self:
            rec.entries_counts = len(rec.acc_moves_ids)

    def button_mark_done(self):
        if self.move_raw_ids.filtered(lambda x: x.product_id and x.change_qty > 0 and x.quantity_approve_state != 'done'):
            raise UserError('Some raw materials have not been approved.')
        if not self.env.context.get('mo_ids_to_backorder') and self.env.context.get('skip_backorder'):
            company = self.env.company
            if not company.mrp_debit_account_id or not company.mrp_credit_account_id or not company.mrp_journal_id:
                raise UserError('Please configure the entry settings for MRP backorder.')
            for rec in self:
                move_id = self.env['account.move'].create([{
                    'move_type': 'entry',
                    'journal_id': company.mrp_journal_id.id,
                    'ref': 'MRP Backorder',
                    'date': fields.Date.today(),
                    'backorder_mrp_id': rec.id,
                    'line_ids': [
                        (0, 0, {
                            'account_id': company.mrp_debit_account_id.id,
                            'name': rec.product_id.name,
                            'product_id': rec.product_id.id,
                            'debit': rec.product_id.lst_price * (rec.product_qty - rec.qty_producing),
                        }),
                        (0, 0, {
                            'account_id': company.mrp_credit_account_id.id,
                            'name': rec.product_id.name,
                            'product_id': rec.product_id.id,
                            'credit': rec.product_id.lst_price * (rec.product_qty - rec.qty_producing),
                        })
                    ]
                }])
        return super().button_mark_done()

    def action_view_backorder_moves(self):
        action = self.env['ir.actions.actions']._for_xml_id('account.action_move_journal_line')
        action['domain'] = [('backorder_mrp_id', 'in', self.ids)]
        action['context'] = {'default_backorder_mrp_id': self.ids[0], 'create': False}
        return action
