# -*- coding: utf-8 -*-
{
    'name': "sale Requests",
    'summary': """
       Complaint Requests
       """,
    'author': "Eslam Moahmed",
    'category': 'Sales',
    'version': '20.0.0.0.1',
    'depends': ['base', 'sale', 'product', 'stock','project'],
    'data': [
        'security/ir.access.csv',
        'views/sales_requests_view.xml',
        'views/sales_requests_lins_view.xml',
        'views/project_task_views.xml',
        'views/menus.xml',
    ],
    'application' :False,
    'installable' :True,
    'auto_install' :False,
}
