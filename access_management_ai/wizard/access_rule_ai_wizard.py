# Copyright (C) NexGen Solutions
from odoo import fields, models, api, _
from odoo.exceptions import UserError


class AccessRuleAiWizard(models.TransientModel):
    _name = 'access.rule.ai.wizard'
    _inherit = ['access.ai.wizard.mixin']
    _description = 'Generate Access Rule with AI'

    prompt = fields.Text(
        "Prompt",
        required=True,
        help="Describe the access restrictions to apply, e.g. Hide Inventory menus and make stock.picking read-only.",
    )
    rule_id = fields.Many2one('access.management', string='Access Rule', readonly=True)
    rule_name = fields.Char(
        string='Rule Name',
        help="Optional suggested name. Leave empty to let AI choose a name from the prompt.",
    )
    create_new = fields.Boolean(
        string='Create New Rule',
        default=False,
        help="When set, AI always creates a new access rule instead of updating the current one.",
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        create_new = bool(
            self.env.context.get('access_rule_ai_create')
            or self.env.context.get('default_create_new')
            or res.get('create_new')
        )
        if create_new:
            res['create_new'] = True
            res['rule_id'] = False
            if 'prompt' in fields_list and not res.get('prompt'):
                res['prompt'] = _(
                    "Create an access rule based on this description. "
                    "Choose a clear rule name and apply matching menu, model, field and UI restrictions."
                )
            return res

        active_model = self.env.context.get('active_model')
        active_id = self.env.context.get('active_id')
        if active_model == 'access.management' and active_id:
            rule = self.env['access.management'].browse(active_id)
            if rule.exists():
                res['rule_id'] = rule.id
                res['rule_name'] = rule.name
                res['create_new'] = False
                if 'prompt' in fields_list and not res.get('prompt'):
                    res['prompt'] = _(
                        "Configure access restrictions that match this rule name: \"%s\". "
                        "Apply sensible menu, model, field and UI restrictions for that purpose."
                    ) % rule.name
        return res

    def _get_schema_instructions(self, rule_name, create_new=False):
        if create_new:
            name_rule = (
                f'- Set "name" to a clear, concise access-rule title derived from the user prompt'
                f'{f" (prefer: {rule_name})" if rule_name else ""}.'
            )
            name_value = rule_name or 'Warehouse Restriction'
            mode_line = 'CREATE a brand-new access rule'
        else:
            name_rule = f'- Keep "name" exactly equal to: {rule_name or "Generated Access Rule"}'
            name_value = rule_name or 'Generated Access Rule'
            mode_line = 'UPDATE an existing access rule'

        return f"""
You are an Odoo 20 access-management expert.
Generate access-rule settings for an Access Management profile.

MODE: {mode_line}
RULE NAME HINT: {rule_name or '(choose from the user prompt)'}

Return ONLY valid JSON. No markdown fences, no explanation.
The JSON MUST be a single object with a "profiles" array containing exactly one profile object.

Use this exact schema (keys must match exactly):
{{
  "profiles": [
    {{
      "name": "{name_value}",
      "readonly": false,
      "global_prevent_login": false,
      "global_hide_import": false,
      "global_hide_export": false,
      "global_hide_print": false,
      "global_hide_action": false,
      "global_hide_chatter": false,
      "restrict_developer_mode": false,
      "menus": ["module.xml_id_of_menu"],
      "reports": ["module.xml_id_of_report"],
      "actions": ["module.xml_id_of_action"],
      "server_actions": [],
      "client_actions": [],
      "url_actions": [],
      "model_access_ids": [
        {{
          "model_name": "stock.picking",
          "perm_create": false,
          "perm_write": false,
          "perm_unlink": false,
          "allow_export": true,
          "allow_archive": true,
          "allow_duplicate": false,
          "hide_import_button": false,
          "hide_print": false,
          "hide_action": false,
          "domain_read": false,
          "domain_write": false,
          "domain_create": false,
          "domain_unlink": false
        }}
      ],
      "field_access_ids": [
        {{
          "model_name": "stock.picking",
          "field_name": "partner_id",
          "is_invisible": false,
          "is_readonly": true,
          "is_required": false
        }}
      ],
      "element_access_ids": [],
      "global_element_ids": []
    }}
  ]
}}

Rules:
{name_rule}
- Prefer real Odoo external IDs (xmlids) for menus/actions/reports when known.
- If an xmlid is unknown, you may use the visible menu/action name instead.
- Put window actions only in "actions", server actions in "server_actions",
  client actions in "client_actions", URL actions in "url_actions",
  and reports only in "reports". Never put a server/client/url/report into "actions".
- Do not invent numeric database IDs. Omit unknown actions rather than guessing.
- Prefer menus + model_access_ids + field_access_ids over uncertain action lists.
- model_name must be a technical model name (e.g. "stock.picking", "product.product").
- field_name must be a technical field name on that model.
- For "hide / restrict / warehouse / inventory / sales / accounting" style names, populate menus and model_access_ids accordingly.
- Only include restrictions that match the rule name and the user prompt.
- Do not invent unrelated apps.
- Leave element_access_ids and global_element_ids empty unless you know exact element_ref values.

USER PROMPT:
"""

    @api.model
    def _normalize_profile(self, profile, force_name=None):
        """Map AI shorthand / legacy keys into the import/export schema."""
        if not isinstance(profile, dict):
            raise UserError(_("AI profile entry must be a JSON object."))

        normalized = dict(profile)

        # Legacy / shorthand aliases -> import keys
        alias_map = {
            'hide_menu_ids': 'menus',
            'hide_menus': 'menus',
            'menu_ids': 'menus',
            'hide_action_ids': 'actions',
            'hide_actions': 'actions',
            'action_ids': 'actions',
            'hide_report_ids': 'reports',
            'hide_reports': 'reports',
            'report_ids': 'reports',
            'hide_server_action_ids': 'server_actions',
            'hide_client_action_ids': 'client_actions',
            'hide_url_action_ids': 'url_actions',
            'disable_login': 'global_prevent_login',
            'prevent_login': 'global_prevent_login',
        }
        for src, dest in alias_map.items():
            if src in normalized and dest not in normalized:
                normalized[dest] = normalized.pop(src)
            elif src in normalized:
                normalized.pop(src, None)

        # hide_model_ids / hide_models -> model_access_ids rows
        hide_models = normalized.pop('hide_model_ids', None)
        if hide_models is None:
            hide_models = normalized.pop('hide_models', None)
        if hide_models:
            model_lines = list(normalized.get('model_access_ids') or [])
            existing = {m.get('model_name') for m in model_lines if isinstance(m, dict)}
            for model_name in hide_models:
                if not model_name or model_name in existing:
                    continue
                model_lines.append({
                    'model_name': model_name,
                    'perm_create': False,
                    'perm_write': False,
                    'perm_unlink': False,
                    'allow_export': False,
                    'allow_archive': False,
                    'allow_duplicate': False,
                    'hide_import_button': True,
                    'hide_print': True,
                    'hide_action': True,
                })
            normalized['model_access_ids'] = model_lines

        # hide_field_ids like "sale.order.amount_total" -> field_access_ids
        hide_fields = normalized.pop('hide_field_ids', None)
        if hide_fields is None:
            hide_fields = normalized.pop('hide_fields', None)
        if hide_fields:
            field_lines = list(normalized.get('field_access_ids') or [])
            existing = {
                (f.get('model_name'), f.get('field_name'))
                for f in field_lines if isinstance(f, dict)
            }
            for raw in hide_fields:
                if not raw or not isinstance(raw, str) or '.' not in raw:
                    continue
                # "sale.order.amount_total" -> model sale.order, field amount_total
                model_name, field_name = raw.rsplit('.', 1)
                key = (model_name, field_name)
                if key in existing:
                    continue
                field_lines.append({
                    'model_name': model_name,
                    'field_name': field_name,
                    'is_invisible': True,
                    'is_readonly': False,
                    'is_required': False,
                })
                existing.add(key)
            normalized['field_access_ids'] = field_lines

        # hide_chatter_model_ids -> per-model chatter hide
        hide_chatter_models = normalized.pop('hide_chatter_model_ids', None)
        if hide_chatter_models:
            model_lines = list(normalized.get('model_access_ids') or [])
            by_model = {
                m.get('model_name'): m for m in model_lines if isinstance(m, dict)
            }
            for model_name in hide_chatter_models:
                if not model_name:
                    continue
                line = by_model.get(model_name)
                if not line:
                    line = {
                        'model_name': model_name,
                        'perm_create': True,
                        'perm_write': True,
                        'perm_unlink': True,
                    }
                    model_lines.append(line)
                    by_model[model_name] = line
                line['chatter_hide'] = True
            normalized['model_access_ids'] = model_lines

        # Drop unknown one2many aliases that the importer ignores
        normalized.pop('hide_view_nodes_ids', None)

        if force_name:
            normalized['name'] = force_name
        elif not normalized.get('name'):
            normalized['name'] = _('Generated Access Rule')

        # Ensure list fields exist so importer clears/rebuilds consistently
        for key in (
            'menus', 'reports', 'actions', 'server_actions', 'client_actions',
            'url_actions', 'model_access_ids', 'field_access_ids',
            'element_access_ids', 'global_element_ids',
        ):
            if key not in normalized:
                normalized[key] = []
            elif normalized[key] is None:
                normalized[key] = []

        return normalized

    def action_generate_rule(self):
        self.ensure_one()

        create_new = bool(self.create_new or self.env.context.get('access_rule_ai_create'))
        existing_rule = False
        if not create_new:
            existing_rule = self.rule_id
            if not existing_rule and self.env.context.get('active_model') == 'access.management':
                active_id = self.env.context.get('active_id')
                if active_id:
                    existing_rule = self.env['access.management'].browse(active_id).exists()

        rule_name = ''
        if existing_rule:
            rule_name = existing_rule.name
        elif self.rule_name:
            rule_name = self.rule_name.strip()

        full_prompt = self._get_schema_instructions(
            rule_name, create_new=bool(create_new or not existing_rule)
        ) + self.prompt

        text_response = self._call_ai(full_prompt)
        parsed = self._extract_json(text_response)

        profiles = parsed.get('profiles') if isinstance(parsed, dict) else None
        if profiles is None and isinstance(parsed, list):
            profiles = parsed
        if not profiles:
            # Allow a bare single profile object
            if isinstance(parsed, dict) and (
                'menus' in parsed or 'model_access_ids' in parsed or 'hide_menu_ids' in parsed
                or 'name' in parsed
            ):
                profiles = [parsed]
            else:
                raise UserError(
                    _("AI returned no profiles.\n\nRaw Response: %s") % text_response
                )

        # Force existing name only when updating; on create prefer AI name (or suggested).
        force_name = existing_rule.name if existing_rule else (rule_name or None)
        normalized_profiles = [
            self._normalize_profile(p, force_name=force_name)
            for p in profiles
        ]

        existing_rule_id = existing_rule.id if existing_rule else None
        try:
            import_wizard = self.env['access.import.export'].create({
                'import_active_status': True,
            })
            created_rule_ids, _logs = import_wizard._process_json_profiles(
                normalized_profiles,
                existing_rule_id=existing_rule_id,
            )
        except UserError:
            raise
        except Exception as e:
            raise UserError(_("Failed to apply AI output to the rule: %s") % str(e))

        if not created_rule_ids:
            raise UserError(_("AI generated empty rules."))

        target_id = existing_rule_id or created_rule_ids[0]
        rule = self.env['access.management'].browse(target_id)

        summary_parts = []
        if rule.menu_ids:
            summary_parts.append(_("%s menus") % len(rule.menu_ids))
        if rule.model_access_ids:
            summary_parts.append(_("%s models") % len(rule.model_access_ids))
        if rule.field_access_ids:
            summary_parts.append(_("%s fields") % len(rule.field_access_ids))
        if rule.action_ids or rule.report_ids or rule.server_action_ids:
            summary_parts.append(
                _("%s actions/reports")
                % (len(rule.action_ids) + len(rule.report_ids) + len(rule.server_action_ids))
            )
        summary = ', '.join(summary_parts) if summary_parts else _('basic settings only')

        # Prefer soft_reload when updating the open form; bare act_window
        # dicts without a `views` key crash web._preprocessAction (.map on undefined).
        if existing_rule_id:
            next_action = {'type': 'ir.actions.client', 'tag': 'soft_reload'}
        else:
            next_action = {
                'type': 'ir.actions.act_window',
                'name': _('Access Rule'),
                'res_model': 'access.management',
                'view_mode': 'form',
                'views': [(False, 'form')],
                'res_id': target_id,
                'target': 'current',
            }

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Access Rule Updated') if existing_rule_id else _('Access Rule Created'),
                'message': _('AI applied settings to "%s" (%s).') % (rule.name, summary),
                'type': 'success',
                'sticky': False,
                'next': next_action,
            },
        }
