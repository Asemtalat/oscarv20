from odoo import api, fields, models
from odoo.tools import formatLang


class QualityCheck(models.Model):
    _inherit = "quality.check"

    done_qty = fields.Float("Done Quantity")

    def do_pass(self):
        res = super(QualityCheck, self).do_pass()
        self.move_line_id.move_id.write({'quantity': self.done_qty})
        # move = self.picking_id.move_ids_without_package.filtered(lambda move: move.product_id == self.product_id)
        # move.write({'quantity':self.done_qty})
        return  res

    def do_fail(self):
        res = super(QualityCheck, self).do_fail()
        self.move_line_id.move_id.write({'quantity':self.done_qty})
        # move = self.picking_id.move_ids_without_package.filtered(lambda move: move.product_id == self.product_id)
        # move.write({'quantity':self.done_qty})
        return  res
