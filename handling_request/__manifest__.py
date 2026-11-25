# -*- coding: utf-8 -*-
{
    'name': 'Handling',
    'version': '1.0',
    'author': 'Raval',
    'category': 'Custom',
    'summary': 'Module for managing handling requests.',
    'description': 'This module allows users to manage handling requests.',
    'depends': ['base', 'raval_request_sales', 'stock', 'sale'],
    'data': [
        'security/ir.access.csv',
        'data/sequence.xml',
        'views/handling_views.xml',
        'views/handling_menu.xml',
        'views/stock_location.xml',
        'views/handling_adjustment.xml',
    ],
    'installable': True,
    'application': True,
}
