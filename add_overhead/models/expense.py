from odoo import models, fields, api


class Expense(models.Model):
    _name = 'expense.expense'
    _rec_name = 'expense'

    expense = fields.Char(string="Expense")