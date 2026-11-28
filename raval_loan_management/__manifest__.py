# -*- coding: utf-8 -*-
{
    'name': 'Loan Management',
    'version': '20.0.1.0.0',
    'summary': 'Manage Loan Requests',
    'description': """Helps you to manage Loan Requests of your company's 
     staff.""",
    'author': "Thomas Edward",
    'company': 'Raval Capital',
    'maintainer': 'Raval Capital',
    'depends': [
        'base', 'hr_payroll', 'hr', 'account',
    ],
    'data': [
        'security/ir.access.csv',
        'data/ir_sequence_data.xml',
        'data/hr_payroll_structure_data.xml',
        'data/hr_salary_rule_data.xml',
        # 'data/hr_payslip_input_type_data.xml',
        'views/hr_employee_views.xml',
        'views/hr_loan_views.xml',
        'views/hr_payroll_structure_views.xml',
        'views/hr_payslip_views.xml',
        'views/hr_salary_rule_views.xml',
        'views/payment_views.xml'
    ],
    'license': 'OPL-1',
    'installable': True,
    'auto_install': False,
    'application': False,
}
