from odoo import models, fields, api


class AddOverhead(models.Model):
    _inherit = 'mrp.workcenter'

    overhead_ids = fields.One2many('over.head', 'work_center_id', string="Overhead")

    @api.onchange('overhead_ids')
    def overhead_amount(self):
        for rec in self:
            total = 0
            for res in rec.overhead_ids:
                total = total + res.amount
            rec.costs_hour = total


class Overhead(models.Model):
    _name = 'over.head'

    expense_id = fields.Many2one('expense.expense', string="Expense")
    amount = fields.Integer(string='Amount')
    work_center_id = fields.Many2one(
        comodel_name='mrp.workcenter',
        string='Work_center_id',
        required=False)
