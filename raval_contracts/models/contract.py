# -*- coding: utf-8 -*-
import re
from datetime import datetime

from odoo import models, fields, api, _


class RavContract(models.Model):
    _name = 'rav.contracts'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Contracts'

    name = fields.Char(default='New')
    partner_id = fields.Many2one(comodel_name='res.partner', required=True)
    date_start = fields.Date(required=True, default=datetime.today())
    date_end = fields.Date(required=True, default=datetime.today())
    fixed_discount =  fields.Float()
    state = fields.Selection(selection=[
        ('run', 'Running'),
        ('exp', 'Expired'),
    ], default='run')

    b_new_branch_1 = fields.Boolean(string='New Branch')
    small_branch_1 = fields.Float(string='Small Branch')
    large_branch_1 = fields.Float(string='Large Branch')

    b_product_coding_2 = fields.Boolean(string='Product coding')
    product_price_2 = fields.Float(string='Product Price')

    b_shelf_rental_3 = fields.Boolean(string='Shelf Rental')
    shelf_rental_price_3 = fields.Float(string='Shelf Rental Price')

    b_advertising_expense_4 = fields.Boolean(string='Advertising Expense')
    advertising_expenses_amount_4 = fields.Float(string='Adv. Expense Amount')

    b_marketing_expenses_5 = fields.Boolean(string='Marketing Expense')
    marketing_expenses_amount_5 = fields.Float(string='Marketing Expense Amount')

    b_hyper_birthday_6 = fields.Boolean(string='Hyper Birthday')
    hyper_birthday_price_6 = fields.Float(string='Hyper Birthday Price')

    b_agenda_expenses_7 = fields.Boolean(string='Agenda Expenses')
    agenda_expenses_amount_7 = fields.Float(string='Agenda Expenses Amount')

    b_black_friday_8 = fields.Boolean(string='Black Friday')
    black_friday_amount_8 = fields.Float(string='Black Friday Amount')

    b_new_year_9 = fields.Boolean(string='New Year')
    new_year_amount_9 = fields.Float(string='New Year Amount')

    b_admin_exp_contract_renewal_10 = fields.Boolean(string='Administrative expenses')
    admin_exp_contract_renewal_amount_10 = fields.Float(string='Administrative expenses amount')

    b_dsupply_discount_11 = fields.Boolean(string='Delay Supply Discount')
    dsupply_discount_amount_11 = fields.Float(string='Delay Supply Discount amount')

    b_price_diff_disc_12 = fields.Boolean(string='Price Difference Discount')
    price_diff_disc_amount_12 = fields.Float(string='Price Difference Discount amount')

    b_nonconformity_disc_13 = fields.Boolean(string='Non-conformity discount')
    nonconformity_disc_amount_13 = fields.Float(string='Non-conformity discount amount')

    b_magazine_offers_delay_disc_14 = fields.Boolean(string='Magazine Offers Delay Discount')
    magazine_offers_delay_disc_amount_14 = fields.Float(string='Magazine Offers Delay Discount amount')

    b_special_product_disc_15 = fields.Boolean(string='Special discount on some products')
    special_product_disc_amount_15 = fields.Float(string='Special discount on some products amount')

    b_tasting_disc_16 = fields.Boolean(string='Discount Tasting Campaigns')
    tasting_disc_amount_16 = fields.Float(string='Discount Tasting Campaigns amount')

    sales_target_lines = fields.One2many(
        comodel_name='sales.target.line',
        inverse_name='contract_id', )

    credit_note_ids = fields.One2many('account.move', 'contract_id')
    credits_count = fields.Integer(compute='_compute_counts')
    sale_order_ids = fields.One2many('sale.order', 'contract_id')
    sale_order_count = fields.Integer(compute='_compute_counts')
    return_sale_order_count = fields.Integer(compute='_compute_counts')

    @api.model
    def check_expired_contracts(self):
        # This method checks if any contracts are expired and updates their state accordingly
        today = fields.Date.today()
        return self.search([('state', '=', 'run'), ('date_end', '<', today)]).write({
            'state': 'exp'
        })

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals['name'] = self.env['ir.sequence'].next_by_code('rav.contracts.seq')
        return super().create(vals_list)

    @api.depends('credit_note_ids', 'sale_order_ids')
    def _compute_counts(self):
        for rec in self:
            rec.credits_count = len(rec.credit_note_ids.filtered(lambda x: x.move_type == 'out_refund'))
            rec.sale_order_count = len(rec.sale_order_ids.filtered(lambda x: not x.return_order))
            rec.return_sale_order_count = len(rec.sale_order_ids.filtered(lambda x: x.return_order))

    def action_open_other_models(self):
        # Open the credit note related to the contract
        # Open the credit note in a new window with the form view for the credit note record
        # and set the target to 'current' to open it in the same window as the contract record
        # This will allow you to see the credit note details in the same window as the contract record,
        # which is useful for auditing and managing the credit note in real-time.
        model_name = self._context.get('model_name')
        sale_type = self._context.get('type', False)
        action = {
            'name': self.env[model_name]._description,
            'type': 'ir.actions.act_window',
            'target': 'current',
            'res_model': model_name,
            'context': {
                'default_contract_id': self.id,
                'default_partner_id': self.partner_id.id
            }
        }
        if model_name == 'account.move':
            record_ids = self.credit_note_ids.filtered(lambda x: x.move_type == 'out_refund').ids
        else:
            if sale_type == 'normal':
                name = 'Sale Orders'
                record_ids = self.sale_order_ids.filtered(lambda x: not x.return_order).ids
            else:
                name = 'Return Sale Orders'
                record_ids = self.sale_order_ids.filtered(lambda x: x.return_order).ids
        if len(record_ids) > 1:
            action['domain'] = [('id', 'in', record_ids)]
            action['view_mode'] = 'list,form'
            return action
        elif len(record_ids) == 1:
            action['res_id'] = record_ids[0]
            action['view_mode'] = 'form'
            return action
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'warning',
                    'sticky': False,
                    'message': _("There\'s no %s on this contract!" % ('Credit notes' if model_name == 'account.move' else name)),
                    'next': {'type': 'ir.actions.act_window_close'},
                }
            }

    def _get_bool_fields_data(self):
        # Get all fields data from the contract
        data = self._fields.items()
        listed_data = list(map(lambda x: x[0], list(data)))
        bool_data = list(filter(lambda x: re.match(r'\bb_\w+_\d+\b', x), listed_data))
        return {
            'listed_data': listed_data,
            'bool_data': bool_data
        }
    
    def action_choose_targets(self):
        # Open a wizard to choose sales targets for the contract
        ctx = {}
        bool_data = self._get_bool_fields_data()['bool_data']
        for i in range(len(bool_data)):
            ctx['default_' + bool_data[i]] = getattr(self, bool_data[i])
        return {
            'type': 'ir.actions.act_window',
            'name': 'Choose Sales Targets',
            'res_model': 'cn.choose.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': ctx,
        }

    def create_credit_note(self, bool_data=False):
        # credit_note = self.env['account.move'].search([('contract_id', '=', self.id)], limit=1)
        # if credit_note:
        #     return self.action_open_credit_note()
        # Create a new credit note for the contract
        listed_data = self._get_bool_fields_data()['listed_data']
        if not bool_data:
            bool_data = self._get_bool_fields_data()['bool_data']
            bool_data = list(filter(lambda x: getattr(self, x), bool_data))
        lines = []
        for i in range(len(bool_data)):
            field_sequence = bool_data[i].split('_')[-1]
            pattern = r'\b\w*_%s\b' % field_sequence
            filtered_data = list(filter(lambda x: re.match(pattern, x), listed_data))
            filtered_data.remove(bool_data[i])
            for fdata in filtered_data:
                lines.append((0, 0, {
                    'name': self._fields[fdata].string,
                    'quantity': 1,
                    'price_unit': getattr(self, fdata),
                    'display_type': 'product'
                }))

        credit_note = self.env['account.move'].create(
            [
                {
                    'partner_id': self.partner_id.id,
                    'contract_id': self.id,
                    'move_type': 'out_refund',
                    'ref': 'Credit Note for Contract %s' % self.name,
                    'line_ids': lines
                }
            ]
        )

        return credit_note

    def create_sale_order(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Sale Order',
            'res_model': 'sale.order',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_contract_id': self.id,
                'default_partner_id': self.partner_id.id,
                'default_origin': self.name,
            },
        }

    def create_return_sale_order(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Sale Order',
            'res_model': 'sale.order',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_contract_id': self.id,
                'default_partner_id': self.partner_id.id,
                'default_origin': self.name,
                'default_return_order': True,
            },
        }
