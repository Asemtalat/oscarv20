# -*- coding: utf-8 -*-
{
    'name': 'Purchase Down Payment',
    'author': "Raval",
    'version': '20.0.1.0.0',
    'depends': ['base', 'purchase'],
    'data': [
        'security/ir.access.csv',
        'views/purchase_order_views.xml',
        'views/res_config_setting_views.xml',
        'wizard/payment_wizard.xml',

    ],
    'application': False,
    'installable': True,
    'auto_install': False,
}
