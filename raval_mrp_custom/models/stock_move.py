from odoo import api, fields, models


class StockMove(models.Model):
    _inherit = 'stock.move'

    change_qty = fields.Float(copy=False)
    quantity_approve_state = fields.Selection([
        ('1st', 'First Approve'),
        ('2nd', 'Second Approve'),
        ('done', 'Approved'),
    ], default='1st', copy=False)

    def action_first_approve(self):
        self.quantity_approve_state = '2nd'

    def action_second_approve(self):
        self.quantity_approve_state = 'done'
        self.quantity = self.change_qty

    @api.depends('move_line_ids.quantity', 'move_line_ids.uom_id')
    def _compute_quantity(self):
        # an approved quantity must not be overwritten by the move lines sum
        approved = self.filtered(lambda move: move.quantity_approve_state == 'done')
        super(StockMove, self - approved)._compute_quantity()
