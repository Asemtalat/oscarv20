# -*- coding: utf-8 -*-
{
    'name': "MRP Custom",

    'depends': ['base', 'mrp', 'account'],

    # always loaded
    'data': [
        'security/ir.access.csv',
        'security/groups.xml',
        'views/mrp.xml',
        'views/config_settings.xml',

        'wizards/warning_wizard.xml',
    ],
}

