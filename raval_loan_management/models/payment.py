# -*- coding: utf-8 -*-

from odoo import fields, models

class AccountPayment(models.Model):
    _inherit = 'account.payment'

    loan_line_id = fields.Many2one('hr.loan.line', string="Loan Line", help="Related Loan Installment")
    loan_id = fields.Many2one('hr.loan', string="Loan", help="Related Loan")
