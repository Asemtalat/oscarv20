from odoo import fields, models, api, _


class InheritPurchase(models.Model):
    _inherit = 'purchase.order'


    downpayment_move_ids = fields.Many2many('account.move', 'purchase_downpayment_move_rel', 'purchase_id', 'downpayment_move_id')
    downpayment_move_count = fields.Integer(compute='_compute_downpayment_move_count')

    def _compute_downpayment_move_count(self):
        for order in self:
            order.downpayment_move_count = len(order.sudo().downpayment_move_ids)


    def down_payment(self):
        return {
            'name': 'payment',
            'type': 'ir.actions.act_window',
            'res_model': 'payment.wizard',
            'view_mode': 'form',
            'context':  {'default_purchase_id': self.id},
            'target': 'new',
            'action': 'new',
        }
    def action_view_downpayment(self):
        return {
            'name': _('Downpayments'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.downpayment_move_ids.ids)],
        }
