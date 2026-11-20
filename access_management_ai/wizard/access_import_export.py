# -*- coding: utf-8 -*-
# Copyright (C) NexGen Solutions
import json
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import BinaryBytes


# Stored scalar fields on access.management (relational / computed handled separately).
PROFILE_SCALARS = [
    'name', 'active', 'sequence', 'readonly',
    'hide_chatter', 'hide_send_message', 'hide_log_note', 'hide_activities', 'hide_followers',
    'global_hide_chatter', 'global_hide_send_message', 'global_hide_log_note',
    'global_hide_activities', 'global_hide_followers',
    'global_hide_import', 'global_hide_print', 'global_hide_action', 'global_hide_export',
    'global_hide_spreadsheet', 'global_hide_filters', 'global_hide_groupby',
    'global_hide_custom_filter', 'global_hide_custom_group',
    'global_hide_favorites', 'global_hide_searchbar', 'global_hide_search_panel', 'global_hide_add_property',
    'global_hide_delete', 'global_hide_filter_delete',
    'global_hide_attachments', 'global_hide_chatter_search',
    'block_module_management',
    'apply_new_internal', 'apply_new_portal',
    'date_start', 'date_end', 'tz', 'time_from', 'time_to',
    'password_expiry_days', 'restrict_developer_mode', 'global_prevent_login',
    'hide_systray_keys',
]

# Stored scalars on access.management.model (M2O names resolved separately).
MODEL_SCALARS = [
    'perm_create', 'perm_write', 'perm_unlink',
    'allow_archive', 'allow_duplicate', 'allow_export',
    'hide_import_button', 'hide_spreadsheet_button', 'hide_print', 'hide_action',
    'hide_tree', 'hide_form', 'hide_kanban', 'hide_calendar', 'hide_pivot',
    'hide_graph', 'hide_gantt', 'hide_map', 'hide_activity', 'hide_hierarchy',
    'hide_searchbar', 'hide_filters', 'hide_groupby',
    'hide_custom_filter', 'hide_custom_group',
    'hide_favorites', 'hide_search_panel', 'hide_add_property',
    'hidden_filter_items', 'hidden_groupby_items',
    'chatter_hide', 'chatter_hide_send_message', 'chatter_hide_log_note',
    'chatter_hide_activities', 'chatter_hide_followers', 'chatter_hide_attachments',
    'chatter_hide_search',
    'domain_read', 'domain_write', 'domain_create', 'domain_unlink',
    'date_filter_period', 'hierarchy_mode',
    'soft_restrict', 'warn_mode', 'warn_message',
]

FIELD_SCALARS = [
    'is_invisible', 'is_readonly', 'is_required',
    'invisible_condition', 'readonly_condition', 'required_condition',
    'remove_external_link', 'no_create', 'domain', 'restrict_export',
]

ELEMENT_SCALARS = ['view_type', 'element_type', 'element_ref', 'invisible_condition']
GLOBAL_ELEMENT_SCALARS = ['view_type', 'element_type', 'element_ref']


class AccessImportExport(models.TransientModel):
    _name = 'access.import.export'
    _description = 'Access Management Import/Export Wizard'

    action = fields.Selection([
        ('export', 'Export Profiles'),
        ('import', 'Import Profiles')
    ], string='Action', default='export', required=True)

    rule_ids = fields.Many2many(
        'access.management',
        string='Profiles to Export'
    )

    file_data = fields.Binary(string='File', attachment=True)
    file_name = fields.Char(string='File Name')
    state = fields.Selection([('init', 'Init'), ('done', 'Done')], default='init')

    import_active_status = fields.Boolean(
        string='Import as Active',
        default=True,
        help="If checked, profiles will be imported exactly as their active state in the file. If unchecked, all profiles will be imported as inactive."
    )
    import_tag_id = fields.Many2one(
        'access.management.tag',
        string='Import Tag',
        help="Tag to apply to all imported profiles for easy identification."
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get('active_model') == 'access.management' and self.env.context.get('active_ids'):
            res['rule_ids'] = [(6, 0, self.env.context.get('active_ids'))]
        return res

    def _get_model_name(self, model_id):
        if not model_id:
            return False
        model = self.env['ir.model'].sudo().browse(model_id)
        return model.model if model.exists() else False

    def _get_field_name(self, field_id):
        if not field_id:
            return False
        field = self.env['ir.model.fields'].sudo().browse(field_id)
        return field.name if field.exists() else False

    @staticmethod
    def _xmlid(record):
        return record.get_external_id().get(record.id) if record else False

    def _field_is_stored(self, Model, field_name):
        field = Model._fields.get(field_name)
        return bool(field and getattr(field, 'store', False))

    def _coerce_ref_list(self, values):
        """Normalize AI/import list values to clean strings."""
        result = []
        for value in values or []:
            if value in (None, False, ''):
                continue
            if isinstance(value, (list, tuple)) and value:
                value = value[0]
            if isinstance(value, dict):
                value = (
                    value.get('xml_id')
                    or value.get('xmlid')
                    or value.get('id')
                    or value.get('name')
                    or value.get('complete_name')
                )
            if value in (None, False, ''):
                continue
            result.append(str(value).strip())
        return result

    def _record_matches_model(self, rec, model_name):
        if not rec or not model_name:
            return False
        if rec._name == model_name:
            return True
        if rec._name == 'ir.actions.actions' and model_name.startswith('ir.actions.'):
            return bool(self.env[model_name].sudo().browse(rec.id).exists())
        return False

    def _match_by_complete_name(self, Model, value):
        """Match non-stored complete_name / display_name in Python (not SQL)."""
        needle = (value or '').strip().lower()
        if not needle or Model is None:
            return Model.browse()
        leaf = needle.split('/')[-1].strip()
        domain = [('name', 'ilike', leaf)] if leaf else []
        candidates = Model.search(domain, limit=80) if domain else Model.browse()
        exact = Model.browse()
        partial = Model.browse()
        for cand in candidates:
            labels = []
            for attr in ('complete_name', 'display_name', 'name'):
                if attr in cand._fields:
                    labels.append((getattr(cand, attr, None) or '').strip().lower())
            if needle in labels:
                exact |= cand
                continue
            if any(needle in label or label.endswith(needle) for label in labels if label):
                partial |= cand
        return exact[:1] or partial[:1]

    def _refs(self, values, model_name=None):
        """Resolve xmlids or display names to database ids for ``model_name`` only."""
        ids = []
        seen = set()
        Model = self.env[model_name].sudo() if model_name else None
        for value in self._coerce_ref_list(values):
            rec = None
            if value.isdigit() and Model is not None:
                cand = Model.browse(int(value))
                if cand.exists():
                    rec = cand
            if not rec and '.' in value and ' ' not in value and '/' not in value:
                cand = self.env.ref(value, raise_if_not_found=False)
                if cand and self._record_matches_model(cand, model_name):
                    rec = Model.browse(cand.id) if Model is not None else cand
                elif cand and Model is not None and cand._name != model_name:
                    rec = None
            if not rec and Model is not None:
                rec = Model.search([('name', '=ilike', value)], limit=1)
                if not rec and self._field_is_stored(Model, 'complete_name'):
                    rec = Model.search([
                        '|',
                        ('complete_name', '=ilike', value),
                        ('complete_name', 'ilike', value),
                    ], limit=1)
                elif not rec and 'complete_name' in Model._fields:
                    rec = self._match_by_complete_name(Model, value)
                if not rec:
                    leaf = value.split('/')[-1].strip()
                    if leaf and leaf.lower() != value.strip().lower():
                        rec = Model.search([('name', '=ilike', leaf)], limit=1)
                if not rec:
                    rec = Model.search([('name', 'ilike', value)], limit=1)
            if rec and self._record_matches_model(rec, model_name) and rec.id not in seen:
                ids.append(rec.id)
                seen.add(rec.id)
        return ids

    _ACTION_BUCKETS = (
        ('ir.actions.act_window', 'action_ids', 'actions'),
        ('ir.actions.server', 'server_action_ids', 'server_actions'),
        ('ir.actions.client', 'client_action_ids', 'client_actions'),
        ('ir.actions.act_url', 'url_action_ids', 'url_actions'),
        ('ir.actions.report', 'report_ids', 'reports'),
    )

    def _resolve_action_buckets(self, profile):
        """Resolve action-like refs and route each record to the correct M2M."""
        buckets = {field: [] for _, field, _ in self._ACTION_BUCKETS}
        seen = {field: set() for field in buckets}
        raw_values = []
        for _model, _field, key in self._ACTION_BUCKETS:
            raw_values.extend(self._coerce_ref_list(profile.get(key)))

        for value in raw_values:
            placed = False
            for model_name, field_name, _key in self._ACTION_BUCKETS:
                ids = self._refs([value], model_name)
                if ids:
                    for rid in ids:
                        if rid not in seen[field_name]:
                            buckets[field_name].append(rid)
                            seen[field_name].add(rid)
                    placed = True
                    break
            if placed:
                continue
            if '.' in value and ' ' not in value and '/' not in value:
                cand = self.env.ref(value, raise_if_not_found=False)
                if not cand:
                    continue
                type_name = getattr(cand, 'type', None) or cand._name
                for model_name, field_name, _key in self._ACTION_BUCKETS:
                    if type_name == model_name or cand._name == model_name:
                        if self.env[model_name].sudo().browse(cand.id).exists() and cand.id not in seen[field_name]:
                            buckets[field_name].append(cand.id)
                            seen[field_name].add(cand.id)
                        break
        return buckets

    def _serialize_scalar(self, record, field_name):
        value = record[field_name]
        field = record._fields[field_name]
        if field.type == 'datetime' and value:
            return fields.Datetime.to_string(value)
        if field.type == 'date' and value:
            return fields.Date.to_string(value)
        return value

    def _resolve_model_field_id(self, model_name, field_name):
        if not model_name or not field_name:
            return False
        field = self.env['ir.model.fields'].sudo().search([
            ('model', '=', model_name),
            ('name', '=', field_name),
        ], limit=1)
        return field.id if field else False

    def _export_profile(self, rule):
        rule_data = {key: self._serialize_scalar(rule, key) for key in PROFILE_SCALARS if key in rule._fields}

        # Relational / assignment
        rule_data['tags'] = rule.tag_ids.mapped('name')
        rule_data['companies'] = rule.company_ids.mapped('name')
        rule_data['users'] = rule.user_ids.mapped('login')
        rule_data['groups'] = [g for g in (self._xmlid(g) for g in rule.group_ids) if g]
        rule_data['custom_groups'] = rule.custom_group_ids.mapped('name')
        rule_data['menus'] = [m for m in (self._xmlid(m) for m in rule.menu_ids) if m]
        rule_data['reports'] = [r for r in (self._xmlid(r) for r in rule.report_ids) if r]
        rule_data['actions'] = [a for a in (self._xmlid(a) for a in rule.action_ids) if a]
        rule_data['server_actions'] = [a for a in (self._xmlid(a) for a in rule.server_action_ids) if a]
        rule_data['client_actions'] = [a for a in (self._xmlid(a) for a in rule.client_action_ids) if a]
        rule_data['url_actions'] = [a for a in (self._xmlid(a) for a in rule.url_action_ids) if a]

        # Backward-compatible alias used by older exports / AI
        rule_data['disable_login'] = rule.global_prevent_login

        # Model Access
        models_data = []
        for line in rule.model_access_ids:
            model_entry = {key: line[key] for key in MODEL_SCALARS if key in line._fields}
            model_entry['model_name'] = line.model_name
            model_entry['date_filter_field'] = line.date_filter_field or False
            model_entry['hierarchy_field'] = line.hierarchy_field or False
            model_entry['hierarchy_user_field'] = line.hierarchy_user_field or False
            model_entry['reports'] = [r for r in (self._xmlid(r) for r in line.report_ids) if r]
            model_entry['actions'] = [a for a in (self._xmlid(a) for a in line.action_ids) if a]
            model_entry['server_actions'] = [a for a in (self._xmlid(a) for a in line.server_action_ids) if a]
            model_entry['client_actions'] = [a for a in (self._xmlid(a) for a in line.client_action_ids) if a]
            model_entry['url_actions'] = [a for a in (self._xmlid(a) for a in line.url_action_ids) if a]
            models_data.append(model_entry)
        rule_data['model_access_ids'] = models_data

        # Field Access
        fields_data = []
        for line in rule.field_access_ids:
            field_entry = {key: line[key] for key in FIELD_SCALARS if key in line._fields}
            field_entry['model_name'] = self._get_model_name(line.model_id.id)
            field_entry['field_name'] = self._get_field_name(line.field_id.id)
            fields_data.append(field_entry)
        rule_data['field_access_ids'] = fields_data

        # Element Access
        elements_data = []
        for line in rule.element_access_ids:
            element_entry = {key: line[key] for key in ELEMENT_SCALARS if key in line._fields}
            element_entry['model_name'] = line.model_name
            elements_data.append(element_entry)
        rule_data['element_access_ids'] = elements_data

        # Global Element Access
        global_elements_data = []
        for line in rule.global_element_ids:
            ge_entry = {key: line[key] for key in GLOBAL_ELEMENT_SCALARS if key in line._fields}
            ge_entry['model_name'] = self._get_model_name(line.model_id.id)
            global_elements_data.append(ge_entry)
        rule_data['global_element_ids'] = global_elements_data

        return rule_data

    def action_export(self):
        if not self.rule_ids:
            raise UserError(_("Please select at least one profile to export."))

        export_data = [self._export_profile(rule) for rule in self.rule_ids]

        json_data = json.dumps(export_data, indent=4)
        encoded_data = BinaryBytes(json_data.encode('utf-8'), filename='access_management_profiles.json')
        self.env['access.audit.log'].create({
            'action': 'workflow',
            'model_name': 'Profile Export Wizard',
            'record_name': 'AccessImportExport',
            'new_value': f"Exported {len(self.rule_ids)} access rules",
            'reason': 'JSON Export',
        })

        self.write({
            'file_data': encoded_data,
            'file_name': 'access_management_profiles.json',
            'state': 'done'
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'access.import.export',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }

    def _prepare_profile_vals(self, profile):
        """Build access.management write/create vals from a profile dict."""
        active_val = profile.get('active', True) if self.import_active_status else False
        vals = {'active': active_val}

        for key in PROFILE_SCALARS:
            if key == 'active':
                continue
            if key in profile:
                vals[key] = profile[key]

        # Older exports / AI used disable_login
        if 'global_prevent_login' not in vals and 'disable_login' in profile:
            vals['global_prevent_login'] = bool(profile.get('disable_login'))

        # Tags from file (by name), optionally merged with wizard import tag
        if 'tags' in profile or self.import_tag_id:
            Tag = self.env['access.management.tag'].sudo()
            tag_ids = set()
            for name in self._coerce_ref_list(profile.get('tags')):
                tag = Tag.search([('name', '=', name)], limit=1)
                if not tag:
                    tag = Tag.create({'name': name})
                tag_ids.add(tag.id)
            if self.import_tag_id:
                tag_ids.add(self.import_tag_id.id)
            if tag_ids:
                vals['tag_ids'] = [(6, 0, list(tag_ids))]

        if 'companies' in profile:
            companies = self.env['res.company'].sudo().search([
                ('name', 'in', self._coerce_ref_list(profile.get('companies'))),
            ])
            vals['company_ids'] = [(6, 0, companies.ids)]

        if 'users' in profile:
            users = self.env['res.users'].sudo().search([
                ('login', 'in', self._coerce_ref_list(profile.get('users'))),
            ])
            vals['user_ids'] = [(6, 0, users.ids)]

        if 'groups' in profile:
            vals['group_ids'] = [(6, 0, self._refs(profile.get('groups', []), 'res.groups'))]

        if 'custom_groups' in profile:
            CustomGroup = self.env['access.management.group'].sudo()
            cg_ids = []
            for name in self._coerce_ref_list(profile.get('custom_groups')):
                group = CustomGroup.search([('name', '=', name)], limit=1)
                if group:
                    cg_ids.append(group.id)
            vals['custom_group_ids'] = [(6, 0, cg_ids)]

        if 'menus' in profile:
            vals['menu_ids'] = [(6, 0, self._refs(profile.get('menus', []), 'ir.ui.menu'))]

        action_keys = (
            'actions', 'server_actions', 'client_actions', 'url_actions', 'reports',
        )
        if any(k in profile for k in action_keys):
            for field_name, ids in self._resolve_action_buckets(profile).items():
                vals[field_name] = [(6, 0, ids)]

        RuleModel = self.env['access.management']
        return {k: v for k, v in vals.items() if k in RuleModel._fields}

    def _prepare_model_line_vals(self, m, rule, model):
        ModelLine = self.env['access.management.model']
        m_vals = {k: m.get(k) for k in MODEL_SCALARS if k in m and k in ModelLine._fields}

        for domain_key in (
            'domain_read', 'domain_write', 'domain_create', 'domain_unlink',
            'warn_message', 'hidden_filter_items', 'hidden_groupby_items',
        ):
            if domain_key in m_vals and m_vals[domain_key] in (False, None, True):
                m_vals.pop(domain_key, None)

        # Resolve related M2O fields from technical names
        date_filter_name = m.get('date_filter_field')
        if date_filter_name:
            field_id = self._resolve_model_field_id(model.model, date_filter_name)
            if field_id:
                m_vals['date_filter_field_id'] = field_id

        hierarchy_name = m.get('hierarchy_field')
        if hierarchy_name:
            field_id = self._resolve_model_field_id(model.model, hierarchy_name)
            if field_id:
                m_vals['hierarchy_field_id'] = field_id

        hierarchy_user_name = m.get('hierarchy_user_field')
        if hierarchy_user_name:
            field_id = self._resolve_model_field_id(model.model, hierarchy_user_name)
            if field_id:
                m_vals['hierarchy_user_field_id'] = field_id

        # Drop related Char fields — they are computed from the M2Os above
        for related_key in ('date_filter_field', 'hierarchy_field', 'hierarchy_user_field', 'model_name'):
            m_vals.pop(related_key, None)

        action_cmds = {}
        for _model_name, field_name, json_key in self._ACTION_BUCKETS:
            refs = self._coerce_ref_list(m.get(json_key))
            m_vals.pop(field_name, None)
            if not refs:
                continue
            ids = self._refs(refs, _model_name)
            if ids:
                action_cmds[field_name] = [(6, 0, ids)]

        m_vals.update({'rule_id': rule.id, 'model_id': model.id})
        m_vals.update(action_cmds)
        return m_vals

    def _process_json_profiles(self, profiles_data, existing_rule_id=None):
        Log = self.env['access.missing.data.log']
        import_log = []
        created_rule_ids = []

        for index, profile in enumerate(profiles_data):
            if not isinstance(profile, dict):
                continue

            vals = self._prepare_profile_vals(profile)

            if existing_rule_id and index == 0 and not vals.get('name'):
                vals.pop('name', None)

            RuleModel = self.env['access.management']
            if existing_rule_id and index == 0:
                rule = RuleModel.browse(existing_rule_id)
                if not rule.exists():
                    raise UserError(_("The access rule to update no longer exists."))
                rule.write(vals)
                rule.model_access_ids.unlink()
                rule.field_access_ids.unlink()
                rule.element_access_ids.unlink()
                rule.global_element_ids.unlink()
            else:
                if not vals.get('name'):
                    vals['name'] = _('Imported Access Rule')
                rule = RuleModel.create(vals)

            created_rule_ids.append(rule.id)

            # Import Model Access
            ModelLine = self.env['access.management.model']
            for m in profile.get('model_access_ids', []) or []:
                if not isinstance(m, dict) or not m.get('model_name'):
                    continue
                model = self.env['ir.model'].search([('model', '=', m['model_name'])], limit=1)
                if not model:
                    log_entry = Log.create({
                        'name': profile.get('name'),
                        'model_name': m.get('model_name'),
                        'missing_type': 'model',
                        'message': f"Model '{m.get('model_name')}' not found."
                    })
                    import_log.append(log_entry)
                    continue
                ModelLine.create(self._prepare_model_line_vals(m, rule, model))

            # Import Field Access
            FieldLine = self.env['access.management.field']
            field_line_fields = set(FieldLine._fields)
            for f in profile.get('field_access_ids', []) or []:
                if not isinstance(f, dict) or not f.get('model_name') or not f.get('field_name'):
                    continue
                model = self.env['ir.model'].search([('model', '=', f['model_name'])], limit=1)
                if not model:
                    log_entry = Log.create({
                        'name': profile.get('name'),
                        'model_name': f.get('model_name'),
                        'field_name': f.get('field_name'),
                        'missing_type': 'model',
                        'message': f"Model '{f.get('model_name')}' not found for field '{f.get('field_name')}'."
                    })
                    import_log.append(log_entry)
                    continue
                field = self.env['ir.model.fields'].search([
                    ('model_id', '=', model.id),
                    ('name', '=', f['field_name']),
                ], limit=1)
                if not field:
                    log_entry = Log.create({
                        'name': profile.get('name'),
                        'model_name': f.get('model_name'),
                        'field_name': f.get('field_name'),
                        'missing_type': 'field',
                        'message': f"Field '{f.get('field_name')}' not found in model '{f.get('model_name')}'."
                    })
                    import_log.append(log_entry)
                    continue
                f_vals = {k: f.get(k) for k in FIELD_SCALARS if k in f and k in field_line_fields}
                for cond_key in ('invisible_condition', 'readonly_condition', 'required_condition', 'domain'):
                    if cond_key in f_vals and f_vals[cond_key] in (False, None, True):
                        f_vals.pop(cond_key, None)
                f_vals.update({'rule_id': rule.id, 'model_id': model.id, 'field_id': field.id})
                FieldLine.create(f_vals)

            # Import Element Access
            ElementLine = self.env['access.management.element']
            element_fields = set(ElementLine._fields)
            for e in profile.get('element_access_ids', []) or []:
                if not isinstance(e, dict) or not e.get('model_name'):
                    continue
                model = self.env['ir.model'].search([('model', '=', e['model_name'])], limit=1)
                if not model:
                    log_entry = Log.create({
                        'name': profile.get('name'),
                        'model_name': e.get('model_name'),
                        'missing_type': 'element',
                        'message': f"Model '{e.get('model_name')}' not found for element '{e.get('element_ref')}'."
                    })
                    import_log.append(log_entry)
                    continue
                e_vals = {k: e.get(k) for k in ELEMENT_SCALARS if k in e and k in element_fields}
                e_vals.update({'rule_id': rule.id, 'model_id': model.id})
                ElementLine.create(e_vals)

            # Import Global Element Access
            GlobalElement = self.env['access.management.global.element']
            global_fields = set(GlobalElement._fields)
            for e in profile.get('global_element_ids', []) or []:
                if not isinstance(e, dict) or not e.get('model_name'):
                    continue
                model = self.env['ir.model'].search([('model', '=', e['model_name'])], limit=1)
                if not model:
                    log_entry = Log.create({
                        'name': profile.get('name'),
                        'model_name': e.get('model_name'),
                        'missing_type': 'element',
                        'message': f"Model '{e.get('model_name')}' not found for global element '{e.get('element_ref')}'."
                    })
                    import_log.append(log_entry)
                    continue
                e_vals = {k: e.get(k) for k in GLOBAL_ELEMENT_SCALARS if k in e and k in global_fields}
                e_vals.update({'profile_id': rule.id, 'model_id': model.id})
                GlobalElement.create(e_vals)

        return created_rule_ids, import_log

    def action_import(self):
        if not self.file_data:
            raise UserError(_("Please upload a file to import."))

        try:
            decoded_data = self.file_data.content.decode('utf-8')
            profiles_data = json.loads(decoded_data)
        except Exception:
            raise UserError(_("Invalid file format. Please upload a valid JSON file."))

        if not isinstance(profiles_data, list):
            raise UserError(_("Invalid file content."))

        _created_rule_ids, import_log = self._process_json_profiles(profiles_data)

        if not import_log:
            self.env['access.audit.log'].create({
                'action': 'workflow',
                'model_name': 'Excel Import Wizard',
                'record_name': 'AccessImportExport',
                'new_value': "Successfully imported access rules",
                'reason': 'Excel Import',
            })
            action = self.env['ir.actions.act_window']._for_xml_id('access_management_ai.action_access_management')
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('Rules imported successfully.'),
                    'type': 'success',
                    'sticky': False,
                    'next': action,
                }
            }

        self.env['access.audit.log'].create({
            'action': 'workflow',
            'model_name': 'Excel Import Wizard',
            'record_name': 'AccessImportExport',
            'new_value': f"Imported access rules with {len(import_log)} missing data errors",
            'reason': 'Excel Import',
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Missing Data Log'),
            'res_model': 'access.missing.data.log',
            'view_mode': 'list,form',
            'target': 'current',
        }
