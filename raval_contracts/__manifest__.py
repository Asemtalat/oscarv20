# -*- coding: utf-8 -*-
{
    'name': "Contracts",

    'depends': ['base', 'account', 'sale', 'return_sale_order'],

    'data': [
        'security/ir.access.csv',

        'data/sequence.xml',
        'data/cron.xml',

        'views/contract.xml',
        'views/sales_target_line.xml',
        'views/sale_order.xml',

        'wizards/cn_choose_wizard.xml',
    ],
}

