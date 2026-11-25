from odoo import models, fields, api, _
from odoo.exceptions import UserError


# class AccountPaymentRegister(models.TransientModel):
#     _inherit = 'account.payment.register'
#
#     check_info = fields.Boolean(string='Check')
#     due_date = fields.Date(string='Due Date')
#     check_number = fields.Char()
#     bank_name = fields.Char()
#
#
#
#     def _create_payment_vals_from_wizard(self, batch_result):
#         # OVERRIDE
#         payment_vals = super()._create_payment_vals_from_wizard(batch_result)
#         if self.check_info:
#             payment_vals['due_date'] = self.due_date
#             payment_vals['check_number'] = self.check_number
#             payment_vals['bank_name'] = self.bank_name
#         return payment_vals
#
#     def _create_payment_vals_from_batch(self, batch_result):
#         """It super the batch action of the create payment values and update
#          the bank and cheque values"""
#         res = super(AccountPaymentRegister,self)._create_payment_vals_from_batch(batch_result)
#         if self.check_info:
#             res.update({
#                 'due_date': self.due_date,
#                 'check_number': self.check_number,
#                 'bank_name': self.bank_name,
#             })
#         return res


class Payment(models.Model):
    _inherit = 'account.payment'

    check_info = fields.Boolean(string='Check')
    due_date = fields.Date(string='Due Date')
    check_number_info = fields.Char()
    bank_name = fields.Char()
