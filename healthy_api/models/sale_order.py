# -*- coding: utf-8 -*-
"""
Extension of the ``sale.order`` model to support additional warehouse
statuses used by the mobile application. The extra field ``warehouse_status``
tracks the progress of an order from the warehouse perspective independently
of the core Odoo state. Possible values include ``draft``, ``prepared``,
``delivered``, ``rejected``, ``ready`` and ``handover`` but no restriction
is imposed on the content so that the front‑end can freely set custom
statuses.
"""

from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    warehouse_status = fields.Selection([
        ('draft', 'Draft'),
        ('prepared', 'Prepared'),
        ('delivered', 'Delivered'),
        ('rejected', 'Rejected'),
        ('ready', 'Ready'),
        ('handover', 'Handover'),
    ], default='draft', string='Warehouse Status', copy=False, tracking=True,
        help='Additional status tracked by the mobile app for warehouse operations.')
    rejection_reason = fields.Text(string='Rejection Reason', copy=False)