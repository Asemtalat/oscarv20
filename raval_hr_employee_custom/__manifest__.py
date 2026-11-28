# -*- coding: utf-8 -*-
{
    'name': "HR Employee Custom",

    'version': '20.0.1.0.0',
    'license': 'LGPL-3',
    'depends': ['base', 'documents', 'hr'],

    # always loaded
    'data': [
        'security/groups.xml',
        'security/ir.access.csv',

        'data/cron_jobs.xml',

        'views/documents.xml',
        'views/settings.xml',
        'views/employee.xml',
        'views/jobs_history.xml',
        'views/department_history.xml',
    ],
}

