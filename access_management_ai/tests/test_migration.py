"""Odoo 20 migration regressions. Run only in an isolated test database."""
import json
import importlib.util
import io
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from lxml import etree

from odoo import Command, fields
from odoo.exceptions import AccessDenied, AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user
from odoo.addons.base.models.ir_module import IrModuleModule as CoreModule
from odoo.addons.base.models.res_config import ResConfigSettings as CoreSettings
from odoo.addons.base_import_module.models.ir_module import IrModuleModule as ImportModule


@tagged('post_install', '-at_install')
class TestAccessManagement20(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context={**cls.env.context, 'tracking_disable': True,
                                   'mail_create_nosubscribe': True})
        # Existing customer profiles must not influence the test fixtures.
        cls.env['access.management'].search([]).write({'active': False})
        cls.user = new_test_user(cls.env, login='am20_regression_user',
                                 groups='base.group_user,base.group_partner_manager,base.group_allow_export')
        cls.manager = new_test_user(cls.env, login='am20_regression_manager',
                                   groups='access_management_ai.group_access_manager')
        cls.partner_model = cls.env['ir.model']._get('res.partner')
        cls.profile = cls.env['access.management'].create({
            'name': 'AM20 regression profile', 'user_ids': [Command.link(cls.user.id)],
        })
        cls.line = cls.env['access.management.model'].create({
            'rule_id': cls.profile.id, 'model_id': cls.partner_model.id,
        })
        cls.allowed = cls.env['res.partner'].create({'name': 'AM20 Allowed', 'user_id': cls.user.id})
        cls.denied = cls.env['res.partner'].create({'name': 'AM20 Denied'})

    def test_crud_and_invalidation(self):
        model = self.env['res.partner'].with_user(self.user)
        self.assertTrue(model.has_access('create'))
        self.line.write({'perm_create': False, 'perm_write': False, 'perm_unlink': False})
        for operation in ('create', 'write', 'unlink'):
            self.assertFalse(model.has_access(operation), operation)
        with self.assertRaises(AccessError):
            model.create({'name': 'Forbidden'})
        with self.assertRaises(AccessError):
            self.allowed.with_user(self.user).write({'name': 'Forbidden'})
        with self.assertRaises(AccessError):
            self.allowed.with_user(self.user).unlink()
        self.line.perm_write = True
        self.assertTrue(self.allowed.with_user(self.user).has_access('write'))

    def test_domains_all_operations(self):
        domain = "[('user_id', '=', uid)]"
        self.line.write(dict.fromkeys(['domain_read', 'domain_write', 'domain_create', 'domain_unlink'], domain))
        for operation in ('read', 'write', 'create', 'unlink'):
            self.assertTrue(self.allowed.with_user(self.user).has_access(operation), operation)
            self.assertFalse(self.denied.with_user(self.user).has_access(operation), operation)
        found = self.env['res.partner'].with_user(self.user).search([('id', 'in', (self.allowed | self.denied).ids)])
        self.assertEqual(found.ids, self.allowed.ids)

    def test_soft_domain_direct_search_and_read(self):
        self.line.write({'soft_restrict': True, 'domain_read': "[('user_id', '=', uid)]"})
        model = self.env['res.partner'].with_user(self.user)
        self.assertEqual(model.search([('id', 'in', (self.allowed | self.denied).ids)]).ids, self.allowed.ids)
        with self.assertRaises(AccessError):
            self.denied.with_user(self.user).read(['name'])

    def test_warn_mode_preserves_native_access(self):
        self.line.write({'warn_mode': True, 'perm_create': False, 'perm_write': False,
                         'perm_unlink': False, 'domain_write': "[('id', '=', 0)]"})
        self.assertTrue(self.allowed.with_user(self.user).has_access('write'))
        self.allowed.with_user(self.user).write({'name': 'Warning allowed'})
        self.assertFalse(self.env['ir.module.module'].with_user(self.user).has_access('create'))

    def test_schedule_not_cached(self):
        now = fields.Datetime.now()
        self.profile.write({'date_start': now + timedelta(hours=1)})
        self.line.perm_write = False
        model = self.env['res.partner'].with_user(self.user)
        with patch.object(fields.Datetime, 'now', return_value=now):
            self.assertTrue(model.has_access('write'))
        with patch.object(fields.Datetime, 'now', return_value=now + timedelta(hours=2)):
            self.assertFalse(model.has_access('write'))

    def test_group_membership_cache(self):
        group = self.env['access.management.group'].create({'name': 'AM20 group'})
        self.profile.write({'user_ids': [Command.clear()], 'custom_group_ids': [Command.link(group.id)]})
        self.line.perm_write = False
        model = self.env['res.partner'].with_user(self.user)
        self.assertTrue(model.has_access('write'))
        group.user_ids = [Command.link(self.user.id)]
        self.assertFalse(model.has_access('write'))
        group.user_ids = [Command.clear()]
        self.assertTrue(model.has_access('write'))
        self.user.access_custom_group_ids = [Command.link(group.id)]
        self.assertFalse(model.has_access('write'))

    def test_global_readonly(self):
        self.profile.readonly = True
        self.assertFalse(self.allowed.with_user(self.user).has_access('write'))
        root = etree.fromstring(self.env['res.partner'].with_user(self.user).get_view(view_type='form')['arch'])
        self.assertEqual(root.get('edit'), '0')
        with self.assertRaises(AccessError):
            self.allowed.with_user(self.user).export_data(['name'])

    def test_export_controls(self):
        self.line.allow_export = False
        with self.assertRaises(AccessError):
            self.allowed.with_user(self.user).export_data(['name'])
        self.line.allow_export = True
        self.env['access.management.field'].create({
            'rule_id': self.profile.id, 'model_id': self.partner_model.id,
            'field_id': self.env['ir.model.fields']._get('res.partner', 'name').id,
            'restrict_export': True,
        })
        self.assertEqual(self.allowed.with_user(self.user).export_data(['name'])['datas'], [['']])
        self.assertFalse(self.allowed.with_user(self.user).fields_get(['name'])['name']['exportable'])

    def test_view_fields_elements_and_chatter(self):
        self.env['access.management.field'].create({
            'rule_id': self.profile.id, 'model_id': self.partner_model.id,
            'field_id': self.env['ir.model.fields']._get('res.partner', 'email').id,
            'is_readonly': True,
        })
        self.profile.global_hide_chatter = True
        root = etree.fromstring(self.env['res.partner'].with_user(self.user).get_view(view_type='form')['arch'])
        self.assertTrue(root.xpath('.//field[@name="email"]'))
        self.assertTrue(all(n.get('readonly') == '1' for n in root.xpath('.//field[@name="email"]')))
        self.assertFalse(root.xpath('.//chatter'))

    def test_selectors(self):
        model = self.env['access.management.model'].with_user(self.manager)
        self.assertTrue(model.get_search_menu_items(self.partner_model.id, 'filter'))
        self.assertTrue(model.get_search_menu_items(self.partner_model.id, 'groupby'))
        element = self.env['access.management.element'].with_user(self.manager)
        for kind in ('button', 'page', 'field'):
            choices = element.get_ui_elements(self.partner_model.id, 'form', kind)
            self.assertTrue(choices, kind)
            self.assertEqual(len(choices), len({c['value'] for c in choices}))

    def test_hierarchy_and_date_domains(self):
        child = self.env['res.partner'].create({'name': 'AM20 child', 'parent_id': self.allowed.id})
        self.line.write({
            'hierarchy_field_id': self.env['ir.model.fields']._get('res.partner', 'parent_id').id,
            'hierarchy_user_field_id': self.env['ir.model.fields']._get('res.partner', 'user_id').id,
            'hierarchy_mode': 'descendants',
        })
        model = self.env['res.partner'].with_user(self.user)
        self.assertEqual(set(model.search([('id', 'in', (self.allowed | self.denied | child).ids)]).ids),
                         set((self.allowed | child).ids))
        self.line.write({'date_filter_field_id': self.env['ir.model.fields']._get('res.partner', 'create_date').id,
                         'date_filter_period': 'today'})
        self.assertIn(self.allowed.id, model.search([]).ids)
        self.line.date_filter_period = 'yesterday'
        self.assertNotIn(self.allowed.id, model.search([]).ids)

    def test_invalid_domain_rejected(self):
        with self.assertRaises(ValidationError):
            self.line.domain_read = "[('missing_am20_field', '=', 1)]"

    def test_roles_grant_revoke(self):
        group = self.env['res.groups'].create({'name': 'AM20 role group'})
        role = self.env['access.role'].create({'name': 'AM20 role', 'group_ids': [Command.link(group.id)]})
        line = self.env['access.role.line'].create({'role_id': role.id, 'user_id': self.user.id})
        self.assertIn(group, self.user.group_ids)
        line.date_to = fields.Date.today() - timedelta(days=1)
        self.assertNotIn(group, self.user.group_ids)
        line.date_to = False
        self.assertIn(group, self.user.group_ids)
        line.unlink()
        self.assertNotIn(group, self.user.group_ids)

    def test_transfer_roundtrip(self):
        self.line.write({'hide_custom_filter': True, 'domain_read': "[('user_id', '=', EU)]"})
        wizard = self.env['access.management.transfer'].create({'profile_ids': [Command.link(self.profile.id)]})
        wizard.action_export()
        data = json.loads(wizard.export_file.content)
        self.assertEqual(data['profiles'][0]['name'], self.profile.name)
        wizard.import_file = wizard.export_file
        action = wizard.action_import()
        profiles = self.env['access.management'].search(action['domain'])
        self.assertTrue(profiles)
        self.assertTrue(profiles.model_access_ids.hide_custom_filter)

    def test_dashboard_and_reports(self):
        self.env.flush_all()
        self.assertTrue(self.env['access.management.report'].search([('rule_id', '=', self.profile.id)]))
        reports = self.env['ir.actions.report'].search([('report_name', 'like', 'access_management_ai.%')])
        self.assertEqual(len(reports), 3)
        role = self.env['access.role'].create({'name': 'AM20 report role'})
        request = self.env['access.request'].create({'role_id': role.id, 'request_reason': 'AM20 test'})
        records = {'access.management': self.profile, 'access.role': role, 'access.request': request}
        for report in reports:
            content, _ = report._render_qweb_html(report.report_name, records[report.model].ids)
            self.assertIn(b'AM20', content)
            if report.model == 'access.management':
                self.assertIn(self.user.name.encode(), content)
                self.assertIn(b'Never', content)

    def test_all_module_views(self):
        views = self.env['ir.ui.view'].search([('id', 'in', self.env['ir.model.data'].search([
            ('module', '=', 'access_management_ai'), ('model', '=', 'ir.ui.view')]).mapped('res_id'))])
        for view in views.filtered(lambda v: v.type != 'qweb' and v.model in self.env):
            with self.subTest(view=view.name):
                result = self.env[view.model].with_user(self.manager).get_view(view.id, view.type)
                self.assertTrue(result['arch'])

    def test_nested_role_changes_sync_parent_users(self):
        group = self.env['res.groups'].create({'name': 'AM20 nested role group'})
        child = self.env['access.role'].create({'name': 'AM20 child role', 'group_ids': [Command.link(group.id)]})
        parent = self.env['access.role'].create({'name': 'AM20 parent role', 'implied_role_ids': [Command.link(child.id)]})
        self.env['access.role.line'].create({'role_id': parent.id, 'user_id': self.user.id})
        self.assertIn(group, self.user.group_ids)
        child.active = False
        self.assertNotIn(group, self.user.group_ids)
        child.active = True
        self.assertIn(group, self.user.group_ids)
        child.unlink()
        self.assertNotIn(group, self.user.group_ids)

    def test_request_approval_and_ownership(self):
        role = self.env['access.role'].create({'name': 'AM20 requested role'})
        request = self.env['access.request'].with_user(self.user).create({
            'role_id': role.id, 'request_reason': 'AM20 request',
        })
        with self.assertRaises(AccessError):
            request.write({'state': 'approved'})
        with self.assertRaises(AccessError):
            request.action_approve()
        # No real email is sent during migration verification.
        with patch.object(type(self.env['mail.template']), 'send_mail', return_value=False):
            request.action_submit()
            self.assertEqual(request.state, 'submitted')
            request.with_user(self.manager).action_approve()
            self.assertEqual(request.state, 'approved')
            self.assertTrue(self.env['access.role.line'].search([('role_id', '=', role.id), ('user_id', '=', self.user.id)]))
            request.with_user(self.manager).action_revoke()
            self.assertEqual(request.state, 'revoked')
        other = self.env['access.request'].create({'role_id': role.id, 'user_id': self.manager.id,
                                                  'request_reason': 'Other user'})
        self.assertFalse(other.with_user(self.user).has_access('read'))

    def test_ai_generated_rule_and_role_apply_without_network(self):
        rule_wizard = self.env['access.rule.ai.wizard'].with_user(self.manager).create({
            'prompt': 'AM20 rule', 'create_new': True,
        })
        payload = {'profiles': [{'name': 'AM20 generated rule', 'model_access_ids': [
            {'model_name': 'res.partner', 'hide_custom_filter': True}]}]}
        with patch.object(type(rule_wizard), '_call_ai', return_value=json.dumps(payload)):
            result = rule_wizard.action_generate_rule()
        rule = self.env['access.management'].browse(result['params']['next']['res_id'])
        self.assertTrue(rule.model_access_ids.hide_custom_filter)
        role_wizard = self.env['access.role.ai.wizard'].with_user(self.manager).create({
            'prompt': 'AM20 role', 'create_new': True,
        })
        with patch.object(type(role_wizard), '_call_ai', return_value=json.dumps({
            'roles': [{'name': 'AM20 generated role', 'groups': ['base.group_user']}],
        })):
            result = role_wizard.action_generate_role()
        role = self.env['access.role'].browse(result['params']['next']['res_id'])
        self.assertIn(self.env.ref('base.group_user'), role.group_ids)

    def test_json_import_export_and_missing_data(self):
        wizard = self.env['access.import.export'].create({'rule_ids': [Command.link(self.profile.id)]})
        self.profile.global_hide_searchbar = True
        wizard.action_export()
        self.assertTrue(json.loads(wizard.file_data.content)[0]['global_hide_searchbar'])
        self.assertEqual(wizard.action_import()['tag'], 'display_notification')
        ids, logs = wizard._process_json_profiles([{'name': 'AM20 missing model', 'model_access_ids': [
            {'model_name': 'am20.nonexistent'}]}])
        self.assertEqual(len(ids), 1)
        self.assertEqual(len(logs), 1)

    def test_mass_assignment(self):
        group = self.env['res.groups'].create({'name': 'AM20 bulk group'})
        wizard = self.env['access.group.assign'].with_user(self.manager).create({
            'user_ids': [Command.link(self.user.id)], 'group_ids': [Command.link(group.id)],
        })
        wizard.action_apply()
        self.assertIn(group, self.user.group_ids)
        wizard.operation = 'remove'
        wizard.action_apply()
        self.assertNotIn(group, self.user.group_ids)

    def test_login_controls_and_password_expiry(self):
        self.user.password = 'am20_test_password'
        credential = {'type': 'password', 'password': 'am20_test_password'}
        user = self.user.with_user(self.user)
        self.assertEqual(user._check_credentials(credential, {'interactive': True})['uid'], self.user.id)
        self.user.access_prevent_login = True
        with self.assertRaises(AccessDenied):
            user._check_credentials(credential, {'interactive': True})
        self.user.access_prevent_login = False
        self.user.access_block_external_api = True
        with self.assertRaises(AccessDenied):
            user._check_credentials(credential, {'interactive': False})
        self.profile.password_expiry_days = 1
        self.user.password_write_date = fields.Datetime.now() - timedelta(days=2)
        with self.assertRaises(AccessDenied):
            user._check_credentials(credential, {'interactive': True})

    def test_json2_api_key_restriction(self):
        keys = self.env['res.users.apikeys'].with_user(self.user)
        key = keys._generate('rpc', 'AM20 verification key', fields.Datetime.now() + timedelta(hours=1))
        self.assertEqual(keys._check_credentials(scope='rpc', key=key), self.user.id)
        self.user.access_block_external_api = True
        self.assertFalse(keys._check_credentials(scope='rpc', key=key))

    def test_scheduled_menus_refresh(self):
        action = self.env['ir.actions.act_window'].create({
            'name': 'AM20 menu action', 'res_model': 'res.partner', 'view_mode': 'list,form',
        })
        menu = self.env['ir.ui.menu'].create({'name': 'AM20 menu', 'action': f'ir.actions.act_window,{action.id}'})
        now = fields.Datetime.now()
        self.profile.write({'menu_ids': [Command.link(menu.id)], 'date_start': now + timedelta(hours=1)})
        menus = self.env['ir.ui.menu'].with_user(self.user)
        with patch.object(fields.Datetime, 'now', return_value=now):
            self.assertIn(menu.id, menus.load_menus(False))
        with patch.object(fields.Datetime, 'now', return_value=now + timedelta(hours=2)):
            self.assertNotIn(menu.id, menus.load_menus(False))

    def test_hidden_actions_and_views(self):
        action = self.env['ir.actions.act_window'].create({
            'name': 'AM20 hidden action', 'res_model': 'res.partner', 'view_mode': 'list,form',
        })
        self.line.hide_form = True
        self.assertEqual(action.with_user(self.user).sudo()._get_action_dict()['view_mode'], 'list')
        self.profile.action_ids = [Command.link(action.id)]
        with self.assertRaises(AccessError):
            action.with_user(self.user).sudo()._get_action_dict()

    def test_saved_filter_delete_restricted(self):
        saved = self.env['ir.filters'].with_user(self.user).create({
            'name': 'AM20 favorite', 'model_id': 'res.partner', 'user_ids': [Command.link(self.user.id)],
            'domain': '[]', 'context': '{}',
        })
        self.profile.global_hide_filter_delete = True
        root = etree.fromstring(saved.get_view(view_type='form')['arch'])
        self.assertEqual(root.get('delete'), '0')
        with self.assertRaises(AccessError):
            saved.unlink()

    def test_legacy_security_conversion_idempotent(self):
        migration_path = Path(__file__).resolve().parents[1] / 'migrations/20.0.1.0.6/pre-migration.py'
        spec = importlib.util.spec_from_file_location('am20_security_migration', migration_path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        cr = self.env.cr
        cr.execute('''CREATE TEMP TABLE ir_model_access (
            id integer PRIMARY KEY, name varchar, active boolean, model_id integer,
            group_id integer, perm_read boolean, perm_write boolean, perm_create boolean, perm_unlink boolean
        ) ON COMMIT DROP''')
        cr.execute('''CREATE TEMP TABLE ir_rule (
            id integer PRIMARY KEY, name varchar, active boolean, model_id integer,
            domain_force text, perm_read boolean, perm_write boolean, perm_create boolean, perm_unlink boolean
        ) ON COMMIT DROP''')
        cr.execute('INSERT INTO ir_model_access VALUES (999001, %s, true, %s, %s, true, true, false, false)',
                   ('AM20 legacy ACL', self.partner_model.id, self.env.ref('base.group_user').id))
        cr.execute('INSERT INTO ir_rule VALUES (999002, %s, true, %s, %s, true, true, true, true)',
                   ('AM20 legacy company rule', self.partner_model.id, "[('company_id', '=', False)]"))
        records = self.env['ir.model.data'].create([
            {'module': 'access_management_ai', 'name': 'am20_legacy_acl_fixture', 'model': 'ir.model.access', 'res_id': 999001},
            {'module': 'access_management_ai', 'name': 'am20_legacy_rule_fixture', 'model': 'ir.rule', 'res_id': 999002},
        ])
        self.env.flush_all()
        migration.migrate(cr, '19.0.1.0.5')
        records.invalidate_recordset()
        self.assertEqual(set(records.mapped('model')), {'ir.access'})
        converted_ids = records.mapped('res_id')
        self.assertEqual(self.env['ir.access'].browse(converted_ids[0]).operation, 'ru')
        self.assertEqual(self.env['ir.access'].browse(converted_ids[1]).domain, "[('company_id', '=', False)]")
        migration.migrate(cr, '19.0.1.0.5')
        records.invalidate_recordset()
        self.assertEqual(records.mapped('res_id'), converted_ids)

    def test_ai_provider_transports_mocked(self):
        wizard = self.env['access.rule.ai.wizard'].with_user(self.manager).create({'prompt': 'AM20 transport'})
        config = self.env['ir.config_parameter']
        config.set_str('access_management_ai.ai_data_consent', 'True')
        responses = {
            'gemini': {'candidates': [{'content': {'parts': [{'text': '{"profiles": []}'}]}}]},
            'claude': {'content': [{'text': '{"profiles": []}'}]},
            'openai': {'choices': [{'message': {'content': '{"profiles": []}'}}]},
        }
        for provider, response in responses.items():
            with self.subTest(provider=provider):
                config.set_str('access_management_ai.ai_provider', provider)
                config.set_str(f'access_management_ai.{provider}_api_key', 'am20_fake_key')
                with patch('urllib.request.urlopen', return_value=io.BytesIO(json.dumps(response).encode())) as send:
                    self.assertEqual(json.loads(wizard._call_ai('AM20 test')), {'profiles': []})
                    self.assertEqual(send.call_count, 1)
        config.set_str('access_management_ai.ai_provider', 'cursor')
        config.set_str('access_management_ai.cursor_api_key', 'am20_fake_key')
        config.set_str('access_management_ai.cursor_base_url', '')
        with patch('odoo.addons.access_management_ai.models.ai_provider_cursor.cursor_generate_text', return_value='{"profiles": []}'):
            self.assertEqual(json.loads(wizard._call_ai('AM20 test')), {'profiles': []})
        config.set_str('access_management_ai.ai_data_consent', 'False')
        with self.assertRaises(UserError):
            wizard._call_ai('AM20 must not send')
        with self.assertRaises(AccessError):
            self.env['access.rule.ai.wizard'].with_user(self.user).create({'prompt': 'Forbidden'})

    def test_cursor_model_list_shapes(self):
        settings = self.env['res.config.settings']
        for payload in ([{'id': 'test-model'}], {'models': [{'id': 'test-model'}]}):
            with patch('urllib.request.urlopen', return_value=io.BytesIO(json.dumps(payload).encode())):
                self.assertEqual(settings._am_fetch_cursor_models_from_api('am20_fake_key')[0]['id'], 'test-model')

    def test_menu_company_switch_and_permission_scope(self):
        company = self.env['res.company'].create({'name': 'AM20 secondary company'})
        self.user.company_ids = [Command.link(company.id)]
        self.profile.company_ids = [Command.link(company.id)]
        self.line.perm_write = False
        action = self.env['ir.actions.act_window'].create({
            'name': 'AM20 company menu action', 'res_model': 'res.partner', 'view_mode': 'list,form',
        })
        menu = self.env['ir.ui.menu'].create({'name': 'AM20 company menu', 'action': f'ir.actions.act_window,{action.id}'})
        self.profile.menu_ids = [Command.link(menu.id)]
        for current_company, hidden in ((self.env.company, False), (company, True), (self.env.company, False)):
            scoped = self.env['res.partner'].with_user(self.user).with_context(allowed_company_ids=current_company.ids)
            self.assertEqual(scoped.has_access('write'), not hidden)
            menus = scoped.env['ir.ui.menu'].load_menus(False)
            self.assertEqual(menu.id not in menus, hidden)
        self.env.flush_all()
        manager_env = self.manager.with_user(self.manager).with_context(allowed_company_ids=self.env.company.ids).env
        self.assertFalse(self.profile.with_env(manager_env).has_access('read'))
        self.assertFalse(self.line.with_env(manager_env).has_access('read'))
        self.assertFalse(manager_env['access.management.report'].search([('rule_id', '=', self.profile.id)]))

    def test_readonly_actual_crud_and_reversal(self):
        model = self.env['res.partner'].with_user(self.user)
        self.profile.readonly = True
        for operation in ('create', 'write', 'unlink'):
            self.assertFalse(model.has_access(operation))
        with self.assertRaises(AccessError):
            model.create({'name': 'Read-only create must fail'})
        with self.assertRaises(AccessError):
            self.allowed.with_user(self.user).write({'name': 'Read-only edit must fail'})
        with self.assertRaises(AccessError):
            self.allowed.with_user(self.user).unlink()
        self.profile.readonly = False
        self.assertTrue(model.has_access('write'))
        self.user.access_read_only = True
        self.assertFalse(model.has_access('write'))
        self.user.access_read_only = False
        self.assertTrue(model.has_access('write'))

    def test_profile_archive_delete_and_reverse_assignment(self):
        model = self.env['res.partner'].with_user(self.user)
        self.profile.readonly = True
        self.assertFalse(model.has_access('write'))
        self.profile.active = False
        self.assertTrue(model.has_access('write'))
        self.profile.active = True
        self.user.access_rule_ids = [Command.clear()]
        self.assertTrue(model.has_access('write'))
        self.user.access_rule_ids = [Command.link(self.profile.id)]
        self.assertFalse(model.has_access('write'))
        self.profile.unlink()
        self.assertTrue(model.has_access('write'))

    def test_group_reverse_assignment_invalidation(self):
        group = self.env['res.groups'].create({'name': 'AM20 reverse membership'})
        self.profile.write({'user_ids': [Command.clear()], 'group_ids': [Command.link(group.id)], 'readonly': True})
        model = self.env['res.partner'].with_user(self.user)
        self.assertTrue(model.has_access('write'))
        group.user_ids = [Command.link(self.user.id)]
        self.assertFalse(model.has_access('write'))
        group.user_ids = [Command.unlink(self.user.id)]
        self.assertTrue(model.has_access('write'))

    def test_bulk_profile_audit_uses_each_records_previous_users(self):
        other = self.env['access.management'].create({'name': 'AM20 second profile', 'user_ids': [Command.link(self.manager.id)]})
        logs = self.env['access.audit.log']
        start = logs.search([], order='id desc', limit=1).id
        (self.profile | other).write({'user_ids': [Command.clear()]})
        removed = logs.search([('id', '>', start), ('action', '=', 'revoke')])
        self.assertEqual(len(removed), 2)
        by_profile = {log.record_name: log.previous_value for log in removed}
        self.assertIn(self.user.name, by_profile[self.profile.name])
        self.assertNotIn(self.manager.name, by_profile[self.profile.name])
        self.assertIn(self.manager.name, by_profile[other.name])

    def test_roles_preserve_preexisting_manual_groups(self):
        group = self.env['res.groups'].create({'name': 'AM20 manually granted'})
        self.user.group_ids = [Command.link(group.id)]
        role = self.env['access.role'].create({'name': 'AM20 overlapping manual role', 'group_ids': [Command.link(group.id)]})
        line = self.env['access.role.line'].create({'role_id': role.id, 'user_id': self.user.id})
        line.unlink()
        self.assertIn(group, self.user.group_ids, 'Revoking a role must preserve groups held before that role')

    def test_future_role_preserves_existing_groups(self):
        group = self.env['res.groups'].create({'name': 'AM20 future manual group'})
        self.user.group_ids = [Command.link(group.id)]
        role = self.env['access.role'].create({'name': 'AM20 future role', 'group_ids': [Command.link(group.id)]})
        self.env['access.role.line'].create({'role_id': role.id, 'user_id': self.user.id,
                                           'date_from': fields.Date.today() + timedelta(days=1)})
        self.assertIn(group, self.user.group_ids)

    def test_overlapping_roles_revoke_only_last_grant(self):
        group = self.env['res.groups'].create({'name': 'AM20 shared role group'})
        roles = self.env['access.role'].create([
            {'name': 'AM20 overlap A', 'group_ids': [Command.link(group.id)]},
            {'name': 'AM20 overlap B', 'group_ids': [Command.link(group.id)]},
        ])
        lines = self.env['access.role.line'].create([{'role_id': role.id, 'user_id': self.user.id} for role in roles])
        lines[0].unlink()
        self.assertIn(group, self.user.group_ids)
        lines[1].unlink()
        self.assertNotIn(group, self.user.group_ids)

    def test_archived_nested_role_stops_its_subtree(self):
        group = self.env['res.groups'].create({'name': 'AM20 deep nested group'})
        leaf = self.env['access.role'].create({'name': 'AM20 leaf', 'group_ids': [Command.link(group.id)]})
        middle = self.env['access.role'].create({'name': 'AM20 middle', 'implied_role_ids': [Command.link(leaf.id)]})
        parent = self.env['access.role'].create({'name': 'AM20 parent', 'implied_role_ids': [Command.link(middle.id)]})
        self.env['access.role.line'].create({'role_id': parent.id, 'user_id': self.user.id})
        self.assertIn(group, self.user.group_ids)
        middle.active = False
        self.assertNotIn(group, self.user.group_ids)
        middle.active = True
        self.assertIn(group, self.user.group_ids)

    def test_role_reassignment_reconciles_both_users(self):
        group = self.env['res.groups'].create({'name': 'AM20 reassigned group'})
        role = self.env['access.role'].create({'name': 'AM20 reassigned role', 'group_ids': [Command.link(group.id)]})
        line = self.env['access.role.line'].create({'role_id': role.id, 'user_id': self.user.id})
        line.user_id = self.manager
        self.assertNotIn(group, self.user.group_ids)
        self.assertIn(group, self.manager.group_ids)

    def test_overnight_schedule_and_end_date(self):
        self.profile.write({'readonly': True, 'tz': 'UTC', 'time_from': 22, 'time_to': 6})
        model = self.env['res.partner'].with_user(self.user)
        for moment, restricted in [('2026-09-18 23:00:00', True), ('2026-09-19 02:00:00', True),
                                   ('2026-09-19 12:00:00', False)]:
            with patch.object(fields.Datetime, 'now', return_value=fields.Datetime.to_datetime(moment)):
                self.env.transaction.invalidate_access_cache()
                self.assertEqual(model.has_access('write'), not restricted)

    def test_multi_profile_denial_wins_over_warn_mode(self):
        other = self.env['access.management'].create({'name': 'AM20 hard deny', 'user_ids': [Command.link(self.user.id)]})
        self.line.write({'warn_mode': True, 'perm_write': False})
        self.env['access.management.model'].create({'rule_id': other.id, 'model_id': self.partner_model.id, 'perm_write': False})
        self.assertFalse(self.allowed.with_user(self.user).has_access('write'))

    def test_export_related_field_restriction(self):
        self.denied.email = 'am20-private@example.invalid'
        self.allowed.parent_id = self.denied
        self.env['access.management.field'].create({'rule_id': self.profile.id, 'model_id': self.partner_model.id,
            'field_id': self.env['ir.model.fields']._get('res.partner', 'email').id, 'restrict_export': True})
        rows = self.allowed.with_user(self.user).export_data(['name', 'parent_id/email'])['datas']
        self.assertEqual(rows[0][1], '', 'Related-field export must respect restrictions on the related model')

    def test_no_manager_methods_for_regular_users(self):
        with self.assertRaises(AccessError):
            self.env['access.group.assign'].with_user(self.user).create({
                'user_ids': [Command.link(self.user.id)],
                'group_ids': [Command.link(self.env.ref('base.group_system').id)],
            }).action_apply()
        with self.assertRaises(AccessError):
            self.env['access.management.transfer'].with_user(self.user).create({}).action_export()
        with self.assertRaises(AccessError):
            self.env['access.import.export'].with_user(self.user).create({}).action_export()

    def test_readonly_blocks_module_changes(self):
        self.manager.access_read_only = True
        module = self.env['ir.module.module'].with_user(self.manager).search([('name', '=', 'access_management_ai')])
        with self.assertRaises(AccessError):
            module.write({'sequence': 99})

    def test_request_cannot_retarget_after_submission(self):
        role = self.env['access.role'].create({'name': 'AM20 immutable requested role'})
        req = self.env['access.request'].with_user(self.user).create({'role_id': role.id, 'request_reason': 'Audit'})
        with patch.object(type(self.env['mail.template']), 'send_mail', return_value=False):
            req.action_submit()
        with self.assertRaises(AccessError):
            req.write({'user_id': self.manager.id})
        with self.assertRaises(AccessError):
            req.write({'role_id': False})

    def test_reject_request_workflow(self):
        role = self.env['access.role'].create({'name': 'AM20 rejected role'})
        req = self.env['access.request'].with_user(self.user).create({'role_id': role.id, 'request_reason': 'Audit rejection'})
        with patch.object(type(self.env['mail.template']), 'send_mail', return_value=False):
            req.action_submit()
            wizard = self.env['access.request.reject'].with_user(self.manager).create({'request_id': req.id, 'reason': 'Not needed'})
            wizard.action_reject()
        self.assertEqual(req.state, 'rejected')
        self.assertFalse(self.env['access.role.line'].search([('role_id', '=', role.id)]))

    def test_readonly_ui_payload_and_module_guard(self):
        self.profile.write({'readonly': True, 'user_ids': [Command.link(self.manager.id)]})
        payload = self.env['res.users'].with_user(self.user).get_access_restrictions()
        for option in ('hide_import', 'hide_export', 'hide_archive', 'hide_delete', 'hide_add_property'):
            self.assertTrue(payload['global'][option], option)
        root = etree.fromstring(self.env['res.partner'].with_user(self.user).get_view(view_type='list')['arch'])
        self.assertEqual(root.get('import'), '0')
        module = self.env['ir.module.module'].with_user(self.manager).search([('name', '=', 'access_management_ai')])
        with self.assertRaises(AccessError):
            module.write({'sequence': 99})

    def test_export_translated_and_disabled_related_model(self):
        field = self.env['ir.model.fields']._get('res.partner', 'name')
        self.env['access.management.field'].create({'rule_id': self.profile.id, 'model_id': self.partner_model.id,
                                                   'field_id': field.id, 'restrict_export': True})
        self.assertEqual(self.allowed.with_user(self.user).export_data(['name@en_US'])['datas'], [['']])
        country = self.env.ref('base.us')
        self.allowed.country_id = country
        self.env['access.management.model'].create({'rule_id': self.profile.id,
            'model_id': self.env['ir.model']._get('res.country').id, 'allow_export': False})
        self.assertEqual(self.allowed.with_user(self.user).export_data(['country_id/name'])['datas'], [['']])

    def test_profile_request_respects_future_start(self):
        future = fields.Date.today() + timedelta(days=2)
        self.profile.user_ids = [Command.clear()]
        req = self.env['access.request'].with_user(self.manager).create({
            'profile_id': self.profile.id, 'user_id': self.user.id, 'request_reason': 'Future profile',
            'date_from': future, 'date_to': future})
        with patch.object(type(self.env['mail.template']), 'send_mail', return_value=False):
            req.action_submit()
            req.action_approve()
        self.assertNotIn(self.user, self.profile.user_ids, 'Future profile grants must wait until their start date')
        with patch.object(type(self.env['mail.template']), 'send_mail', return_value=False):
            with patch.object(fields.Date, 'context_today', return_value=future):
                self.env['access.request']._cron_check_expiring_access()
                self.assertIn(self.user, self.profile.user_ids)
            with patch.object(fields.Date, 'context_today', return_value=future + timedelta(days=1)):
                self.env['access.request']._cron_check_expiring_access()
                self.assertNotIn(self.user, self.profile.user_ids)
                self.assertEqual(req.state, 'expired')

    def test_profile_request_revoke_preserves_manual_assignment(self):
        req = self.env['access.request'].with_user(self.manager).create({
            'profile_id': self.profile.id, 'user_id': self.user.id, 'request_reason': 'Already assigned profile'})
        with patch.object(type(self.env['mail.template']), 'send_mail', return_value=False):
            req.action_submit()
            req.action_approve()
            req.action_revoke()
        self.assertIn(self.user, self.profile.user_ids, 'Revoking a request must preserve a previous manual assignment')

    def test_profile_requests_overlap_until_last_revocation(self):
        self.profile.user_ids = [Command.clear()]
        reqs = self.env['access.request'].with_user(self.manager).create([
            {'profile_id': self.profile.id, 'user_id': self.user.id, 'request_reason': 'Overlap A'},
            {'profile_id': self.profile.id, 'user_id': self.user.id, 'request_reason': 'Overlap B'},
        ])
        with patch.object(type(self.env['mail.template']), 'send_mail', return_value=False):
            reqs.action_submit()
            reqs.action_approve()
            reqs[0].action_revoke()
            self.assertIn(self.user, self.profile.user_ids)
            reqs[1].action_revoke()
            self.assertNotIn(self.user, self.profile.user_ids)

    def test_role_request_revokes_only_its_original_assignment(self):
        role = self.env['access.role'].create({'name': 'AM20 owned request role'})
        req = self.env['access.request'].with_user(self.manager).create({
            'role_id': role.id, 'user_id': self.user.id, 'request_reason': 'Tracked grant'})
        with patch.object(type(self.env['mail.template']), 'send_mail', return_value=False):
            req.action_submit()
            req.action_approve()
            req.granted_role_line_id.unlink()
            replacement = self.env['access.role.line'].create({'role_id': role.id, 'user_id': self.user.id})
            req.action_revoke()
            self.assertTrue(replacement.exists())

    def test_request_approved_details_and_deletion_guard(self):
        role = self.env['access.role'].create({'name': 'AM20 protected approval'})
        req = self.env['access.request'].with_user(self.manager).create({
            'role_id': role.id, 'user_id': self.user.id, 'request_reason': 'Immutable approval'})
        with patch.object(type(self.env['mail.template']), 'send_mail', return_value=False):
            req.action_submit()
            req.action_approve()
        with self.assertRaises(UserError):
            req.user_id = self.manager
        with self.assertRaises(UserError):
            req.unlink()

    def test_request_existing_role_is_rejected_cleanly(self):
        role = self.env['access.role'].create({'name': 'AM20 preexisting role'})
        line = self.env['access.role.line'].create({'role_id': role.id, 'user_id': self.user.id})
        req = self.env['access.request'].with_user(self.manager).create({
            'role_id': role.id, 'user_id': self.user.id, 'request_reason': 'Duplicate role'})
        with patch.object(type(self.env['mail.template']), 'send_mail', return_value=False):
            req.action_submit()
            with self.assertRaises(UserError):
                req.action_approve()
        self.assertEqual(req.state, 'submitted')
        self.assertTrue(line.exists())

    def test_conditional_fields_load_missing_view_dependencies(self):
        view = self.env['ir.ui.view'].create({'name': 'AM20 conditional dependency form',
            'model': 'res.partner', 'type': 'form',
            'arch': '<form><field name="name"/><field name="email"/></form>'})
        self.env['access.management.field'].create({'rule_id': self.profile.id, 'model_id': self.partner_model.id,
            'field_id': self.env['ir.model.fields']._get('res.partner', 'email').id,
            'is_invisible': True, 'invisible_condition': "[('is_company', '=', True)]"})
        result = self.env['res.partner'].with_user(self.user).get_views([[view.id, 'form']])
        root = etree.fromstring(result['views']['form']['arch'])
        self.assertTrue(root.xpath('./field[@name="is_company"][@invisible="1"]'))
        self.assertIn('is_company', result['models']['res.partner']['fields'])

    def test_field_restrictions_respect_embedded_model_scope(self):
        view = self.env['ir.ui.view'].create({'name': 'AM20 embedded scope form', 'model': 'res.partner',
            'type': 'form', 'arch': '''<form><field name="name"/>
                <field name="category_id"><list><field name="name"/></list></field>
                <field name="bank_ids"><list><field name="account_number"/></list></field></form>'''})
        self.env['access.management.field'].create([
            {'rule_id': self.profile.id, 'model_id': self.partner_model.id,
             'field_id': self.env['ir.model.fields']._get('res.partner', 'name').id, 'is_readonly': True},
            {'rule_id': self.profile.id, 'model_id': self.env['ir.model']._get('res.partner.bank').id,
             'field_id': self.env['ir.model.fields']._get('res.partner.bank', 'account_number').id, 'is_readonly': True},
        ])
        result = self.env['res.partner'].with_user(self.user).get_view(view.id, 'form')
        root = etree.fromstring(result['arch'])
        self.assertEqual(root.xpath('./field[@name="name"]')[0].get('readonly'), '1')
        self.assertNotEqual(root.xpath('.//field[@name="category_id"]//field[@name="name"]')[0].get('readonly'), '1')
        self.assertEqual(root.xpath('.//field[@name="account_number"]')[0].get('readonly'), '1')

    def test_conditional_fields_do_not_break_search_views(self):
        view = self.env['ir.ui.view'].create({'name': 'AM20 condition search',
            'model': 'res.partner', 'type': 'search',
            'arch': '<search><field name="email"/><field name="phone"/></search>'})
        self.env['access.management.field'].create([
            {'rule_id': self.profile.id, 'model_id': self.partner_model.id,
             'field_id': self.env['ir.model.fields']._get('res.partner', 'email').id,
             'is_invisible': True, 'invisible_condition': "[('ref', '=', 'AM20_HIDE')]"},
            {'rule_id': self.profile.id, 'model_id': self.partner_model.id,
             'field_id': self.env['ir.model.fields']._get('res.partner', 'phone').id,
             'is_invisible': True},
        ])
        result = self.env['res.partner'].with_user(self.user).get_view(view.id, 'search')
        root = etree.fromstring(result['arch'])
        self.assertFalse(root.xpath('./field[@name="email"]')[0].get('invisible'))
        self.assertEqual(root.xpath('./field[@name="phone"]')[0].get('invisible'), '1')

    def _module_block_admin(self):
        self.manager.group_ids = [Command.link(self.env.ref('base.group_system').id)]
        self.profile.write({'readonly': False, 'block_module_management': True,
                            'user_ids': [Command.link(self.manager.id)]})
        return self.env['ir.module.module'].with_user(self.manager)

    def test_module_block_all_entry_points_and_reversal(self):
        modules = self._module_block_admin()
        for method in ('button_install', 'button_upgrade', 'button_uninstall',
                       'button_immediate_install', 'button_immediate_upgrade',
                       'button_immediate_uninstall', 'button_uninstall_wizard',
                       'module_uninstall', 'update_list'):
            with self.subTest(method=method), patch.object(CoreModule, method, return_value=True) as native:
                with self.assertRaises(AccessError):
                    getattr(modules, method)()
                native.assert_not_called()
        with patch.object(ImportModule, 'button_immediate_install_app', return_value=True) as native:
            with self.assertRaises(AccessError):
                modules.button_immediate_install_app()
            native.assert_not_called()
        self.profile.block_module_management = False
        with patch.object(CoreModule, 'button_immediate_install', return_value=True) as native:
            self.assertTrue(modules.button_immediate_install())
            native.assert_called_once()

    def test_module_block_zip_import_before_privilege_elevation(self):
        modules = self._module_block_admin()
        with patch.object(ImportModule, '_import_zipfile', return_value=True) as importer:
            with self.assertRaises(AccessError):
                modules._import_zipfile(io.BytesIO(b'not consumed'))
            importer.assert_not_called()
            self.profile.block_module_management = False
            self.assertTrue(modules._import_zipfile(io.BytesIO(b'not consumed')))
            importer.assert_called_once()

    def test_module_block_settings_changes(self):
        self._module_block_admin()
        settings = self.env['res.config.settings'].with_user(self.manager).create({})
        modules = settings._get_classified_fields()['module']
        candidate = modules.filtered(lambda m: m.state == 'uninstalled')[:1]
        self.assertTrue(candidate)
        settings[f'module_{candidate.name}'] = True
        with patch.object(CoreSettings, 'execute', return_value=True) as native:
            with self.assertRaises(AccessError):
                settings.execute()
            native.assert_not_called()
            settings[f'module_{candidate.name}'] = False
            self.assertTrue(settings.execute(), 'Unrelated settings remain editable')
            native.assert_called_once()

    def test_module_block_views_menus_and_restoration(self):
        modules = self._module_block_admin()
        for view_type in ('form', 'list', 'kanban'):
            root = etree.fromstring(modules.get_view(view_type=view_type)['arch'])
            self.assertFalse(root.xpath('.//*[@type="object"][@name="button_immediate_install" or @name="button_immediate_upgrade" or @name="button_uninstall_wizard" or @name="button_immediate_install_app"]'))
            self.assertEqual(root.get('delete'), '0')
        menus = self.env['ir.ui.menu'].with_user(self.manager)
        visible = menus._visible_menu_ids(debug=True)
        for xmlid in ('base.menu_view_base_module_update', 'base_import_module.menu_view_base_module_import'):
            self.assertNotIn(self.env.ref(xmlid).id, visible)
        settings_arch = self.env['res.config.settings'].with_user(self.manager).get_view(view_type='form')['arch']
        fields = etree.fromstring(settings_arch).xpath('.//field[starts-with(@name,"module_")]')
        self.assertTrue(fields)
        self.assertTrue(all(node.get('readonly') == '1' for node in fields))
        self.profile.block_module_management = False
        restored = etree.fromstring(modules.get_view(view_type='form')['arch'])
        self.assertTrue(restored.xpath('.//button[@name="button_immediate_install"]'))
        self.assertIn(self.env.ref('base.menu_view_base_module_update').id, menus._visible_menu_ids(debug=True))

    def test_audit_migration_restores_metadata_and_grant_tracking(self):
        group = self.env['res.groups'].create({'name': 'AM20 migrated role group'})
        role = self.env['access.role'].create({'name': 'AM20 migrated role', 'group_ids': [Command.link(group.id)]})
        request = self.env['access.request'].with_user(self.manager).create({
            'role_id': role.id, 'user_id': self.user.id, 'request_reason': 'Legacy request'})
        with patch.object(type(self.env['mail.template']), 'send_mail', return_value=False):
            request.action_submit()
            request.action_approve()
        request.granted_role_line_id = False
        self.user.access_role_managed_group_ids = [Command.clear()]
        module = self.env['ir.module.module'].search([('name', '=', 'access_management_ai')])
        if 'module_type' in module._fields:
            module.module_type = False
        path = Path(__file__).resolve().parents[1] / 'migrations/20.0.1.0.8/post-migration.py'
        spec = importlib.util.spec_from_file_location('am20_audit_migration', path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        self.env.flush_all()
        migration.migrate(self.env.cr, '20.0.1.0.7')
        self.env.invalidate_all()
        self.assertIn(group, self.user.access_role_managed_group_ids)
        self.assertTrue(request.granted_role_line_id)
        if 'module_type' in module._fields:
            self.assertEqual(module.module_type, 'official')
