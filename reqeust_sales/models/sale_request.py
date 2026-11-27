from odoo import models, fields, api


class SalesRequests(models.Model):
    _name = 'sale.request'
    _description = 'Sale Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'create_uid'
    scheduled_date = fields.Date("Scheduled Date")
    location_ids = fields.Many2many('stock.location', string="Locations",
                                    help="If a quality check fails, a location is chosen from this list for each failed quantity.")
    request_line_ids = fields.One2many('sale.request.line', 'request_id', string="Request Lines")


class SalesRequestLines(models.Model):
    _name = 'sale.request.line'
    _description = "Sale Request Line"

    request_id = fields.Many2one('sale.request', string="Sale Request")
    product_id = fields.Many2one('product.product', string="Product")
    quantity = fields.Float("Quantity")
    uom_id = fields.Many2one('uom.uom', string="Unit of Measure")
    available_qty = fields.Float("Available Quantity")