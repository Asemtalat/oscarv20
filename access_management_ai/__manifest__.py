# -*- coding: utf-8 -*-
# Copyright (C) NexGen Solutions
{
    'name': 'User Access Management AI-Powered & Permission Manager',
    'version': '20.0.1.0.10',
    'category': 'Extra Tools',
    'summary': (
        'User Access Manager, No-code access rights and security roles: hide menus, fields, buttons '
        'and views; control record rules, import/export and user permissions.'
    ),
    'description': """
Access Management AI for Odoo 20
================================

Configure detailed access rights for users and groups from one no-code interface.
Control what users can see and do across Odoo models, menus, records, fields,
views, actions and chatter without editing XML or Python files.

Use AI to create, analyze and optimize Odoo 20 access rules. Control menus, models, fields, buttons, views, records, users and groups with intelligent permission management.

Key features
------------
* Hide menus, submenus, apps, actions and view modes per user or security role
* Manage access rights and user permissions without custom development
* Hide, make read-only or required any field on any model conditionally
* Hide buttons and form tabs; restrict chatter features
* Restrict export, import, archive, duplicate, delete and create actions
* Apply record rules / domain filters to restrict visible records
* Optional AI-assisted rule and role generation (OpenAI, Gemini, Claude or Cursor)
* Reusable security roles, bulk assignment, audit logs and access dashboards
* Password expiry, session controls and multi-language support

External services
-----------------
* Optional AI generation is opt-in. Administrator prompts and access-rule or role
  schemas may be sent to the configured external AI provider. Core access control
  works without any external AI service.
""",


    'author': 'NexGen Solutions',
    'website': 'https://nexgensolutions.odoo.com',
    'maintainer': 'NexGen Solutions',
    'support': 'nexgensolutionsodoo@gmail.com',
    'license': 'OPL-1',
    'price': 0.0,
    'currency': 'USD',
    'depends': ['base', 'web', 'mail', 'base_import_module'],
    'data': [
        'security/access_groups.xml',
        'security/access_rules.xml',
        'security/ir.access.csv',
        'data/access_management_data.xml',
        'data/access_role_cron.xml',
        'data/ir_cron_data.xml',
        'data/mail_template_data.xml',
        'data/access_request_data.xml',
        'wizard/access_rule_ai_wizard_views.xml',
        'wizard/access_role_ai_wizard_views.xml',
        'views/access_management_views.xml',
        'views/access_role_views.xml',
        'views/access_group_views.xml',
        'views/access_log_views.xml',
        'views/access_audit_log_views.xml',
        'views/access_request_views.xml',
        'views/access_report_views.xml',
        'views/res_users_views.xml',
        'wizard/access_transfer_views.xml',
        'wizard/group_assign_views.xml',
        'wizard/access_import_export_views.xml',
        'wizard/access_element_selector_views.xml',
        'views/missing_data_log_views.xml',
        'views/access_tag_views.xml',
        'views/res_config_settings_views.xml',
        'report/access_rule_report.xml',
        'report/access_role_report.xml',
        'report/access_request_report.xml',
    ],
    'demo': [
        'demo/access_management_demo.xml',
    ],
    'images': [
        # Browse cards use the declared *_screenshot image as their thumbnail.
        'static/description/main_screenshot.gif',
        'static/description/main_banner.gif',
        'static/description/banner.png',
        'static/description/main_overview.png',
        'static/description/main_screen.png',
        'static/description/icon.png',
        'static/description/ai_rules_roles.png',
    ],
    'assets': {
        'web.assets_backend': [
            'access_management_ai/static/src/access_management.scss',
            'access_management_ai/static/src/access_management.js',
            'access_management_ai/static/src/sync_service.js',
            'access_management_ai/static/src/archive_patch.js',
            'access_management_ai/static/src/chatter_service.js',
            'access_management_ai/static/src/properties_patch.js',
            'access_management_ai/static/src/action_patch.js',
            'access_management_ai/static/src/search_patch.js',
            'access_management_ai/static/src/search_bar_menu_patch.xml',
            'access_management_ai/static/src/search_items_selector.js',
            'access_management_ai/static/src/search_items_selector.xml',
            'access_management_ai/static/src/spreadsheet_patch.js',
            'access_management_ai/static/src/systray_patch.js',
            'access_management_ai/static/src/switch_user_menu.js',
            'access_management_ai/static/src/switch_user_menu.xml',
            'access_management_ai/static/src/warn_mode_patch.js',
            'access_management_ai/static/src/dynamic_element_selection.js',
            'access_management_ai/static/src/dynamic_element_selection.xml',
            'access_management_ai/static/src/systray_selector.js',
            'access_management_ai/static/src/systray_selector.xml',
            'access_management_ai/static/src/export_patch.js',
        ],
    },
    'sequence': 1,
    'application': True,
    'installable': True,
    'auto_install': False,
}
