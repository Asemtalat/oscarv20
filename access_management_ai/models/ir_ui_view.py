# Copyright (C) NexGen Solutions
import ast
import logging

from lxml import etree

from odoo import api, models
from odoo.tools.view_validation import get_expression_field_names

_logger = logging.getLogger(__name__)


def _scope_xpath(root, expression, **kwargs):
    """Select nodes belonging to this view, excluding embedded child views."""
    result = []
    for node in root.xpath(expression, **kwargs):
        for ancestor in node.iterancestors():
            if ancestor is root:
                result.append(node)
                break
            if ancestor.tag in ('form', 'list', 'kanban'):
                break
    return result


def _combine_modifier(node, attr, expr):
    """ OR-combine a view modifier (invisible/readonly/required/column_invisible)
    already present on ``node`` with ``expr`` ("1" to force, or a Python expr). """
    existing = node.get(attr)
    if expr == '1' or existing in ('1', 'True'):
        node.set(attr, '1')
    elif not existing or existing in ('0', 'False'):
        node.set(attr, expr)
    else:
        node.set(attr, '(%s) or (%s)' % (existing, expr))


def _merge_options(node, extra):
    """ Merge ``extra`` dict into the node's ``options`` attribute. """
    options = {}
    raw = node.get('options')
    if raw:
        try:
            options = ast.literal_eval(raw)
            if not isinstance(options, dict):
                return
        except Exception:  # noqa: BLE001 - leave complex/dynamic options untouched
            return
    options.update(extra)
    node.set('options', repr(options))


def _domain_to_condition(domain_str):
    """ Parse a domain string and convert it into a Python expression for UI modifiers. """
    if not domain_str or not str(domain_str).strip().startswith('['):
        return domain_str
    try:
        domain = ast.literal_eval(domain_str)
        if not isinstance(domain, list):
            return domain_str
    except Exception:
        return domain_str

    stack = []
    for item in reversed(domain):
        if item == '!':
            if stack:
                expr = stack.pop()
                stack.append(f"not ({expr})")
        elif item == '|':
            if len(stack) >= 2:
                expr1 = stack.pop()
                expr2 = stack.pop()
                stack.append(f"({expr1} or {expr2})")
        elif item == '&':
            if len(stack) >= 2:
                expr1 = stack.pop()
                expr2 = stack.pop()
                stack.append(f"({expr1} and {expr2})")
        elif isinstance(item, (tuple, list)) and len(item) == 3:
            field, op, val = item
            if op == '=':
                op = '=='
            elif op not in ('==', '!=', '>', '<', '>=', '<=', 'in', 'not in'):
                # Fallback for unsupported JS client-side evaluation operators
                pass
            if isinstance(val, str):
                val = repr(val)
            elif val is True:
                val = "True"
            elif val is False:
                val = "False"
            elif val is None:
                val = "False"
            stack.append(f"{field} {op} {val}")

    if len(stack) == 1:
        return stack[0]
    elif len(stack) > 1:
        return " and ".join(reversed(stack))
    return ''


class Base(models.AbstractModel):
    _inherit = 'base'

    # ------------------------------------------------------------------
    @api.model
    def get_view(self, view_id=None, view_type='form', **options):
        result = super().get_view(view_id, view_type, **options)
        if self.env.su:
            return result

        rules = self.env['access.management']._rules_for_user(self.env.uid)
        read_only = self.env.user.sudo().access_read_only or any(r.readonly for r in rules)
        if not rules and not read_only:
            return result

        model = result.get('model') or self._name
        try:
            root = etree.fromstring(result['arch'])
        except Exception:  # noqa: BLE001
            return result

        def apply_scope(scope, model_name, scope_type):
            self._access_management_apply_fields(scope, rules, model_name, scope_type)
            self._access_management_apply_elements(scope, rules, model_name, scope_type)
            self._access_management_apply_root_attrs(scope, rules, model_name, scope_type, read_only)
            self._access_management_apply_chatter(scope, rules, model_name)
            self._access_management_apply_search(scope, rules, model_name, scope_type)
            for node in _scope_xpath(scope, './/field'):
                field = self.env[model_name]._fields.get(node.get('name'))
                if field and field.relational and field.comodel_name:
                    for child in node:
                        if child.tag in ('form', 'list', 'kanban'):
                            apply_scope(child, field.comodel_name, child.tag)

        apply_scope(root, model, view_type)
        if read_only or any(rule.block_module_management for rule in rules):
            module_buttons = {
                'ir.module.module': {
                    'button_install', 'button_immediate_install', 'button_upgrade',
                    'button_immediate_upgrade', 'button_uninstall', 'button_immediate_uninstall',
                    'button_uninstall_wizard', 'button_immediate_install_app', 'update_list',
                },
                'base.module.uninstall': {'action_uninstall'},
                'base.module.update': {'update_module'},
                'base.import.module': {'import_module'},
            }
            for node in root.xpath('.//*[@type="object"]'):
                if node.get('name') in module_buttons.get(model, set()):
                    node.getparent().remove(node)
            if model == 'ir.module.module' and view_type in ('form', 'list', 'kanban'):
                for attr in ('create', 'edit', 'delete', 'import'):
                    root.set(attr, '0')
            if model == 'res.config.settings':
                for node in _scope_xpath(root, './/field[starts-with(@name, "module_")]'):
                    node.set('readonly', '1')
        self._access_management_modifier_dependencies(root, result)

        result['arch'] = etree.tostring(root, encoding='unicode')
        return result

    def _access_management_modifier_dependencies(self, root, result):
        """Load condition fields in each view scope, including embedded views."""
        model_fields = {name: set(names) for name, names in result.get('models', {}).items()}
        view_tags = {'form', 'list', 'kanban'}

        def process(scope, model, parent_needed=None):
            present, needed = set(), set()

            def visit(node):
                if node.tag == 'field' and node.get('name'):
                    present.add(node.get('name'))
                for attr in ('invisible', 'readonly', 'required', 'domain'):
                    expr = node.get(attr)
                    if expr:
                        for name in get_expression_field_names(expr):
                            if name.startswith('parent.') and parent_needed is not None:
                                parent_needed.add(name.split('.')[1])
                            else:
                                needed.add(name)
                for child in node:
                    if child.tag in view_tags and node.tag == 'field':
                        field = model._fields.get(node.get('name'))
                        if field and field.relational and field.comodel_name:
                            process(child, self.env[field.comodel_name], needed)
                    else:
                        visit(child)

            visit(scope)
            for name in sorted(needed - present):
                if name not in model._fields:
                    continue
                attrs = {'name': name, 'invisible': '1'}
                if scope.tag == 'list':
                    attrs['column_invisible'] = '1'
                scope.append(etree.Element('field', **attrs))
                model_fields.setdefault(model._name, set()).add(name)

        if root.tag in view_tags:
            process(root, self)
            result['models'] = model_fields

    @api.model
    @api.readonly
    def get_views(self, views, options=None):
        result = super().get_views(views, options=options)
        if self.env.su or not (options or {}).get('toolbar'):
            return result

        rules = self.env['access.management']._rules_for_user(self.env.uid)
        if not rules:
            return result
        hidden_reports = self.env['access.management']._hidden_action_ids_for_user(
            self.env.uid, model_name=self._name, action_field='report_ids',
        )
        hidden_actions = self.env['access.management']._hidden_action_ids_for_user(
            self.env.uid, model_name=self._name,
        ) - hidden_reports

        model_hide_print = False
        model_hide_action = False
        for line in rules.model_access_ids:
            if line.model_name == self._name:
                if line.hide_print:
                    model_hide_print = True
                if line.hide_action:
                    model_hide_action = True

        global_hide_print = any(r.global_hide_print for r in rules) or model_hide_print
        global_hide_action = any(r.global_hide_action for r in rules) or model_hide_action

        if not hidden_reports and not hidden_actions and not global_hide_print and not global_hide_action:
            return result

        for view in result.get('views', {}).values():
            toolbar = view.get('toolbar')
            if not toolbar:
                continue
            if global_hide_print and 'print' in toolbar:
                toolbar['print'] = []
            elif hidden_reports and toolbar.get('print'):
                toolbar['print'] = [a for a in toolbar['print'] if a.get('id') not in hidden_reports]

            if global_hide_action and 'action' in toolbar:
                toolbar['action'] = []
            elif hidden_actions and toolbar.get('action'):
                toolbar['action'] = [a for a in toolbar['action'] if a.get('id') not in hidden_actions]
        return result

    # ------------------------------------------------------------------
    def _access_management_apply_fields(self, root, rules, model, view_type):
        inv_attr = 'column_invisible' if view_type == 'list' else 'invisible'
        for line in rules.field_access_ids:
            if line.model_name != model:
                continue
            nodes = _scope_xpath(root, './/field[@name=$name]', name=line.field_name)
            for node in nodes:
                inv_cond = _domain_to_condition(line.invisible_condition) if line.invisible_condition else False
                if view_type == 'search':
                    # Search fields have no current record. Record-dependent
                    # modifiers belong to record views; search rules control
                    # filter visibility separately.
                    if line.is_invisible and not inv_cond:
                        _combine_modifier(node, 'invisible', '1')
                    continue
                # Record-dependent modifiers cannot be evaluated at column
                # scope: the list renderer has no current record there.
                node_inv_attr = 'invisible' if view_type == 'list' and inv_cond else inv_attr
                if line.is_invisible:
                    _combine_modifier(node, node_inv_attr, inv_cond or '1')
                elif inv_cond:
                    _combine_modifier(node, node_inv_attr, inv_cond)
                
                ro_cond = _domain_to_condition(line.readonly_condition) if line.readonly_condition else False
                if line.is_readonly:
                    _combine_modifier(node, 'readonly', ro_cond or '1')
                elif ro_cond:
                    _combine_modifier(node, 'readonly', ro_cond)
                
                req_cond = _domain_to_condition(line.required_condition) if line.required_condition else False
                if line.is_required:
                    _combine_modifier(node, 'required', req_cond or '1')
                elif req_cond:
                    _combine_modifier(node, 'required', req_cond)
                extra = {}
                if line.remove_external_link:
                    extra['no_open'] = True
                if line.no_create:
                    extra['no_create'] = True
                    extra['no_quick_create'] = True
                if extra:
                    _merge_options(node, extra)
                if line.domain:
                    node.set('domain', line.domain)

    def _access_management_apply_elements(self, root, rules, model, view_type):
        tag_by_type = {'button': 'button', 'page': 'page', 'field': 'field'}
        global_refs = {
            g_el.element_ref.strip() 
            for rule in rules 
            for g_el in rule.global_element_ids 
            if g_el.element_ref and g_el.view_type in ('any', view_type)
        }
        for ref in global_refs:
            for tag in ('button', 'page', 'a'):
                for node in _scope_xpath(root,
                        './/%s[@name=$ref or @string=$ref or @title=$ref]' % tag,
                        ref=ref):
                    _combine_modifier(node, 'invisible', '1')
        for line in rules.element_access_ids:
            if line.model_name != model:
                continue
            if line.view_type not in ('any', view_type):
                continue
            expr = line.invisible_condition or '1'
            if expr != '1':
                expr = _domain_to_condition(expr)
            ref = line.element_ref
            tag = tag_by_type.get(line.element_type, '*')
            # match by name attribute or by visible string/label
            nodes = _scope_xpath(root,
                './/%s[@name=$ref or @string=$ref]' % tag, ref=ref)
            if not nodes and line.element_type == 'kanban_link':
                nodes = _scope_xpath(root, './/a[@name=$ref or @type=$ref]', ref=ref)
            for node in nodes:
                _combine_modifier(node, 'invisible', expr)

    def _access_management_apply_root_attrs(self, root, rules, model, view_type, read_only):
        if root.tag not in ('form', 'list', 'kanban', 'tree'):
            return
        lines = rules.model_access_ids.filtered(lambda l: l.model_name == model)
        global_hide_import = any(r.global_hide_import for r in rules)
        global_hide_export = any(r.global_hide_export for r in rules)
        global_hide_delete = any(r.global_hide_delete for r in rules)
        if read_only:
            root.set('create', '0')
            root.set('edit', '0')
            root.set('delete', '0')
            root.set('duplicate', '0')
            if view_type == 'list':
                root.set('export_xlsx', '0')
        if global_hide_delete or (model == 'ir.filters' and any(r.global_hide_filter_delete for r in rules)):
            root.set('delete', '0')
        if global_hide_export and view_type == 'list':
            root.set('export_xlsx', '0')
        if (read_only or global_hide_import) and view_type in ('list', 'kanban'):
            root.set('import', '0')
        for line in lines:
            if not line.perm_create and not line.warn_mode:
                root.set('create', '0')
            if not line.perm_write and not line.warn_mode:
                root.set('edit', '0')
            if not line.perm_unlink and not line.warn_mode:
                root.set('delete', '0')
            if not line.allow_duplicate:
                root.set('duplicate', '0')
            if not line.allow_export and view_type == 'list':
                root.set('export_xlsx', '0')
            if line.hide_import_button and view_type in ('list', 'kanban'):
                root.set('import', '0')

    def _access_management_apply_chatter(self, root, rules, model):
        hide = any(r.hide_chatter or r.global_hide_chatter for r in rules) or any(
            line.model_name == model and line.chatter_hide
            for line in rules.model_access_ids)
        if not hide:
            return
        for node in _scope_xpath(root, './/chatter'):
            node.getparent().remove(node)
        for node in _scope_xpath(root, ".//div[contains(@class, 'oe_chatter')]"):
            node.getparent().remove(node)

    def _access_management_apply_search(self, root, rules, model, view_type):
        if view_type != 'search':
            return
        hide_panel = any(r.global_hide_search_panel for r in rules) or any(
            line.model_name == model and line.hide_search_panel
            for line in rules.model_access_ids)
        if hide_panel:
            for node in root.xpath('.//searchpanel'):
                node.getparent().remove(node)
