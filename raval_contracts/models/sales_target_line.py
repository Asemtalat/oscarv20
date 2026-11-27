from datetime import datetime

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class SalesTargetLine(models.Model):
    _name = 'sales.target.line'
    _description = 'SalesTargetLine'

    contract_id = fields.Many2one('rav.contracts')

    name = fields.Selection([
        ('monthly', 'Monthly Incentive Discount'),
        ('return', 'Discount on Return Percentage'),
    ], required=1)
    start_date = fields.Date()
    end_date = fields.Date()
    period_type = fields.Selection([
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
    ], required=1)
    discount_type = fields.Selection([
        ('percentage', 'Percentage'),
        ('fixed_amount', 'Fixed Amount'),
    ], required=1)

    limit_rate_return_so = fields.Float(string='Limit Rate Return SO')
    rate_return_so = fields.Float(string='Rate Return SO', compute='_compute_total_rso', store=1)
    target_amount = fields.Float(string='Target Amount', required=1)
    discount_amount = fields.Float()
    rate = fields.Float()
    total = fields.Float(string='Total Amount', compute='_compute_total_amount', store=1)
    total_so = fields.Float(string='Total Sale Order', compute='_compute_total_so', store=1)

    detailed_sale_orders = fields.One2many('detailed.sale.order', 's_target_line_id')

    def divide_dates(self, start_date, end_date, period_type):
        periods = []

        # Ensure the dates are in datetime format
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, "%Y-%m-%d")
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, "%Y-%m-%d")

        current_date = start_date

        # Divide based on period type
        if period_type == "yearly":
            while current_date < end_date:
                next_date = current_date + relativedelta(years=1)
                if next_date > end_date:
                    next_date = end_date
                periods.append((current_date, next_date))
                current_date = next_date

        elif period_type == "monthly":
            while current_date < end_date:
                next_date = current_date + relativedelta(months=1)
                if next_date > end_date:
                    next_date = end_date
                periods.append((current_date, next_date))
                current_date = next_date

        return periods

    def recompute_detailed_lines(self):
        orders = self.contract_id.sale_order_ids.filtered(lambda x: x.state == 'sale')

        rso_amount = sum(orders.filtered(lambda x: x.return_order).mapped('amount_total'))
        so_amount = sum(orders.filtered(lambda x: not x.return_order).mapped('amount_total'))

        # end_date = max(orders.filtered(lambda x: not x.return_order).mapped('date_order'))
        # if not end_date:
        #     raise ValidationError('There\'s no sale order is confirmed!')
        periods = self.divide_dates(self.start_date, self.end_date, self.period_type)
        if not periods:
            raise ValidationError('No period is generated!\nPlease check the start date ... it should be before the end date of the sale order!')
        if self.detailed_sale_orders.credit_note_id:
            self.detailed_sale_orders.credit_note_id.unlink()
        self.detailed_sale_orders = [(5, 0, 0)]
        for start_date, end_date in periods:
            sale_orders = orders.filtered(lambda x: not x.return_order and start_date <= x.date_order.date() <= end_date)
            so_total_amount = sum(sale_orders.mapped('amount_total'))
            if self.name == 'monthly':
                # total_comm = so_total_amount if self.rate_return_so > 0.1 else so_total_amount * self.rate_return_so
                if self.discount_type == 'percentage':
                    total_comm = so_total_amount * self.rate
                else:
                    total_comm = self.discount_amount
            else:
                if self.rate_return_so <= self.limit_rate_return_so:
                    if self.discount_type == 'percentage':
                        total_comm = (so_amount - rso_amount) * self.rate
                    else:
                        total_comm = self.discount_amount
                else:
                    total_comm = 0
            detailed_sale_orders = [(0, 0, {
                'date_from': start_date,
                'date_to': end_date,
                'total_sale_orders_amount': total_comm,
            })]
            self.write({
                'detailed_sale_orders': detailed_sale_orders
            })

    def show_detailed_sale_orders(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Detailed Sale Orders',
            'view_mode': 'form',
            'target': 'new',
            'res_model': self._name,
            'res_id': self.id,
        }

    @api.depends('discount_type', 'discount_amount', 'target_amount', 'rate')
    def _compute_total_amount(self):
        for line in self:
            if line.discount_type == 'percentage':
                line.total = line.target_amount * (1 - line.rate)
            else:
                line.total = line.target_amount - line.discount_amount

    @api.depends('contract_id.sale_order_ids.amount_total', 'contract_id.sale_order_ids.state', 'start_date')
    def _compute_total_so(self):
        for line in self:
            line.total_so = sum(line.contract_id.sale_order_ids.filtered(lambda x: not x.return_order).mapped('amount_total'))


    @api.depends('contract_id.sale_order_ids.amount_total', 'contract_id.sale_order_ids.state', 'start_date')
    def _compute_total_rso(self):
        for line in self:
            rso_amount = sum(line.contract_id.sale_order_ids.filtered(lambda x: x.return_order and x.state == 'sale').mapped('amount_total'))
            so_amount = sum(line.contract_id.sale_order_ids.filtered(lambda x: not x.return_order and x.state == 'sale').mapped('amount_total'))
            line.rate_return_so = rso_amount / so_amount if so_amount > 0 else 0.0


