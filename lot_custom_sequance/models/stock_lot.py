from odoo import models, fields, api

class StockLotSerial(models.Model):
    _inherit = 'stock.lot'
    _rec_name = 'display_complete_name'
    _rec_names_search = ['display_complete_name']

    display_complete_name = fields.Char(
        string="Lot/Serial Number - Barcode",
        compute='_compute_display_complete_name',
        store=True
    )

    @api.depends('product_id.barcode','product_id','name')
    def _compute_display_complete_name(self):
        for lot in self:
            if lot.product_id:
                barcode = lot.product_id.barcode
                if barcode:
                    lot.display_complete_name = f"{lot.name}-{barcode}"
                else:
                    lot.display_complete_name = f"{lot.name}"

