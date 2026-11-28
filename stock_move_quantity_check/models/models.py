from odoo import models, _
from odoo.exceptions import UserError

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def _check_quantity_deviation(self):
        for move in self.move_ids:
            if move.picking_id.purchase_id and move.product_uom_qty:
                max_allowed = move.product_uom_qty * 1.10
                if move.quantity > max_allowed:
                    raise UserError(_(
                        "You cannot validate this move. The done quantity (%.2f) "
                        "exceeds the planned quantity (%.2f) by more than 10%%."
                    ) % (move.quantity, move.product_uom_qty))

    def button_validate(self):
        self._check_quantity_deviation()
        return super().button_validate()

