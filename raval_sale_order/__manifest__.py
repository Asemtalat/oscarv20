# -*- coding: utf-8 -*-
{
    'name': "return sale order",
    'summary': """
        return sale order""",
    'author': "Eslam Moahmed",
    'category': 'Sales',
    'version': '20.0.0.0.6',
    'depends': ['base', 'hr', 'product', 'sale', 'sales_team', 'account'],
    'data': [

        'views/return_sale_order_views.xml',
        'views/pricelist_item.xml',
        'views/res_partner_view.xml',
    ],
    'application': False,
    'installable': True,
    'auto_install': False,
}
