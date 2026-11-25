# -*- coding: utf-8 -*-
{
    'name': "Request Sales",

    'depends': ['base', 'product', 'stock', 'purchase'],
    'version': "20.0.1.0.0",
    # always loaded
    'data': [
        'security/ir.access.csv',
        'security/groups.xml',
        'data/sequence.xml',

        'views/request_sales.xml',
        'views/res_users.xml',
        'views/request_sales_lines.xml',

        'wizard/create_po_wiz.xml',
    ],
}
