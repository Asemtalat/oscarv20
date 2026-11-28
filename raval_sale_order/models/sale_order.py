# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.tools import float_round, format_amount


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    payment_term_id = fields.Many2one(
        comodel_name='account.payment.term',
        string="Payment Terms", store=True, readonly=False, check_company=True,  # Unrequired company
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")

    sales_person = fields.Many2one(
        'hr.employee', string="Sales Person", store=True, readonly=False, check_company=True,
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")

    sales_person_id = fields.Many2one(
        'res.partner', string="Sales Person", store=True, readonly=False,
        check_company=True,
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")

    def action_confirm(self):
        for order in self:
            if not order.sales_person and order.user_id.employee_ids:
                order.sales_person = order.user_id.employee_ids[0]
        return super().action_confirm()

    def _prepare_invoice(self):
        invoice_vals = super()._prepare_invoice()
        invoice_vals['sales_person_id'] = self.sales_person_id.id
        return invoice_vals


class AccountMove(models.Model):
    _inherit = 'account.move'

    sales_person_id = fields.Many2one(
        'res.partner', string="Sales Person", store=True, readonly=False,
        check_company=True,
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")


class ProductPricelistItem(models.Model):
    _inherit = 'product.pricelist.item'

    # Odoo 20 reworked pricelist rules: ``compute_price`` is now one of
    # ``discount`` / ``markup`` / ``fixed`` and the percentage lives in
    # ``price_discount``.  The "Discount Type" below only applies to rules
    # with ``compute_price == 'discount'``.
    discount_type = fields.Selection(
        [('percent', 'Percentage'), ('amount', 'Fixed Amount')],
        string="Discount Type",
        default='percent',
    )
    amount_discount = fields.Float(
        string="Amount Discount",
        digits='Product Price',
    )

    @api.onchange('compute_price')
    def _onchange_compute_price_extend(self):
        if self.compute_price != 'discount':
            self.update({
                'discount_type': 'percent',
                'amount_discount': 0.0,
            })

    @api.onchange('discount_type')
    def _onchange_discount_type(self):
        if self.discount_type == 'percent':
            self.amount_discount = 0.0
        else:
            self.price_discount = 0.0

    def _is_amount_discount(self):
        self.ensure_one()
        return self.compute_price == 'discount' and self.discount_type == 'amount'

    @api.depends('discount_type', 'amount_discount')
    def _compute_price_label(self):
        super()._compute_price_label()
        for item in self:
            if not item._is_amount_discount():
                continue
            base_label = item._get_price_label_base_str()
            amount = format_amount(item.env, abs(item.amount_discount), item.currency_id)
            if item.amount_discount >= 0:
                item.price = _("%(amount)s off the %(base)s", amount=amount, base=base_label)
            else:
                item.price = _("%(amount)s added to the %(base)s", amount=amount, base=base_label)

    def _compute_price(self, product, quantity, uom, **kwargs):
        if not self or not self._is_amount_discount():
            return super()._compute_price(product, quantity, uom, **kwargs)
        self.ensure_one()
        product.ensure_one()
        uom = uom or product._get_main_uom()
        uom.ensure_one()

        product_uom = product.uom_id
        base_price = self._compute_base_price(product, quantity, uom, **kwargs)
        price = base_price - product_uom._compute_price(self.amount_discount, uom)
        # same post-processing as the standard discount rule
        if self.price_round:
            price = float_round(price, precision_rounding=self.price_round)
        if self.price_surcharge:
            price += product_uom._compute_price(self.price_surcharge, uom)
        if self.price_min_margin:
            price = max(price, base_price + product_uom._compute_price(self.price_min_margin, uom))
        if self.price_max_margin:
            price = min(price, base_price + product_uom._compute_price(self.price_max_margin, uom))
        return price

    def _show_discount(self):
        """Let a plain fixed-amount rule be displayed on the sale order line as
        the equivalent percentage (Odoo computes it from the base price and the
        pricelist price)."""
        if not self:
            return False
        self.ensure_one()
        if (
            self._is_amount_discount()
            and self.amount_discount > 0
            and not (self.price_round or self.price_surcharge
                     or self.price_min_margin or self.price_max_margin)
        ):
            return self._is_discount_feature_enabled()
        return super()._show_discount()


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    @api.depends('order_id.partner_id')
    def _compute_discount(self):
        super()._compute_discount()
        for line in self:
            partner = line.order_id.partner_id
            if (
                partner.allow_discount
                and line.product_id
                and not line.display_type
                and not line.discount
            ):
                line.discount = partner.discount_rate or 0.0


class CrmTeam(models.Model):
    _inherit = 'crm.team'

    member_employee_ids = fields.Many2many(
        comodel_name='hr.employee',
        string='Salespersons')
