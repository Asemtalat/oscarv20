# -*- coding: utf-8 -*-
{
    'name': 'Working Schedule Shift Rotation',
    'summary': '4-week shift rotation for working schedules',
    'version': '20.0.1.0.0',
    'category': 'Human Resources',
    'depends': ['resource', 'hr_holidays', 'hr_attendance', 'hr_work_entry'],
    'data': [
        'security/ir.access.csv',
        'views/resource_calendar_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
