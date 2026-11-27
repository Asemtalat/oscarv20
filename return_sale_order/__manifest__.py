# -*- coding: utf-8 -*-
{
    'name': "return sale order",
    'summary': """
        return sale order""",
    'author': "Eslam Moahmed",
    'category': 'Sales',
    'version': '20.0.0.0.1',
    'depends': ['base', 'sale', 'product', 'sale_stock' , 'stock'],
    'data': [
        'data/ir_sequence_data.xml',

        'views/return_sale_order_views.xml',
        'views/res_config_setting_views.xml',
        'views/menus.xml',
    ],
    'application' :False,
    'installable' :True,
    'auto_install' :False,
}
