from odoo import fields, models, api, _


class InheritPurchase(models.Model):
    _inherit = 'purchase.order'
    # purchase_ids = fields.One2many('payment.wizard', 'purchase_id')
    payment_term_id = fields.Many2one(
        comodel_name='account.payment.term',
        string="Payment Terms", store=True, readonly=False, check_company=True,  # Unrequired company
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")

    # def down_payment(self):
    #     return {
    #         'name': 'payment',
    #         'type': 'ir.actions.act_window',
    #         'res_model': 'payment.wizard',
    #         'view_mode': 'form',
    #         'context': {'default_purchase_id': self.id},
    #         'target': 'new',
    #         'action': 'new',
    #     }
