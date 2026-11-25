# -*- coding: utf-8 -*-
{
    'name': 'Employee Document',
    'author': "Esalm Mohamed",
    'version': '20.0.1.0.0',
    'depends': ['base', 'hr'],
    'data': [
        'security/ir.access.csv',
        'views/hr_document_views.xml',
        'views/hr_document_line_views.xml',
        'views/hr_employee_views.xml',

    ],
    'application': False,
    'installable': True,
    'auto_install': False,
}
