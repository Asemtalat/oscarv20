# Copyright (C) NexGen Solutions
from odoo import fields, models, api, _
from odoo.exceptions import UserError


class AccessRoleAiWizard(models.TransientModel):
    _name = 'access.role.ai.wizard'
    _inherit = ['access.ai.wizard.mixin']
    _description = 'Generate Security Role with AI'

    prompt = fields.Text(
        "Prompt",
        required=True,
        help="Describe the role to create, e.g. Warehouse manager with inventory and stock groups.",
    )
    role_id = fields.Many2one('access.role', string='Role', readonly=True)
    role_name = fields.Char(
        string='Role Name',
        help="Optional suggested name. Leave empty to let AI choose a name from the prompt.",
    )
    create_new = fields.Boolean(
        string='Create New Role',
        default=False,
        help="When set, AI always creates a new role instead of updating the current one.",
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        create_new = bool(
            self.env.context.get('access_role_ai_create')
            or self.env.context.get('default_create_new')
            or res.get('create_new')
        )
        if create_new:
            res['create_new'] = True
            res['role_id'] = False
            if 'prompt' in fields_list and not res.get('prompt'):
                res['prompt'] = _(
                    "Create a security role based on this description. "
                    "Choose a clear role name and assign the matching Odoo security groups."
                )
            return res

        active_model = self.env.context.get('active_model')
        active_id = self.env.context.get('active_id')
        if active_model == 'access.role' and active_id:
            role = self.env['access.role'].browse(active_id)
            if role.exists():
                res['role_id'] = role.id
                res['role_name'] = role.name
                res['create_new'] = False
                if 'prompt' in fields_list and not res.get('prompt'):
                    res['prompt'] = _(
                        "Configure security groups for this role: \"%s\". "
                        "Pick sensible Odoo groups (and optional included roles) for that job."
                    ) % role.name
        return res

    def _get_schema_instructions(self, role_name, create_new=False):
        if create_new:
            name_rule = (
                f'- Set "name" to a clear, concise role title derived from the user prompt'
                f'{f" (prefer: {role_name})" if role_name else ""}.'
            )
            name_value = role_name or 'Warehouse Manager'
        else:
            name_rule = f'- Keep "name" exactly equal to: {role_name or "Generated Role"}'
            name_value = role_name or 'Generated Role'

        return f"""
You are an Odoo 20 security expert.
Generate a Security Role (bundle of res.groups) for Access Management.

MODE: {"CREATE a brand-new role" if create_new else "UPDATE an existing role"}
ROLE NAME HINT: {role_name or '(choose from the user prompt)'}

Return ONLY valid JSON. No markdown fences, no explanation.
The JSON MUST be a single object with a "roles" array containing exactly one role object.

Use this exact schema (keys must match exactly):
{{
  "roles": [
    {{
      "name": "{name_value}",
      "comment": "Short description of what this role is for",
      "groups": [
        "base.group_user",
        "stock.group_stock_user"
      ],
      "implied_roles": []
    }}
  ]
}}

Rules:
{name_rule}
- "groups" must list Odoo security groups as xmlids (preferred) or display names
  like "Inventory / Administrator" or "Sales / User: All Documents".
- Prefer real xmlids when known (module.group_xmlid). Do not invent numeric IDs.
- Include every group needed for the described job (at least base.group_user when relevant).
- Only include groups that match the role purpose; do not dump unrelated apps.
- "implied_roles" may list other access.role names that already exist; leave empty if unsure.
- "comment" should be one short sentence.
- Do not assign users; only name, comment, groups and included roles.

USER PROMPT:
"""

    @api.model
    def _normalize_role_payload(self, data, force_name=None):
        if not isinstance(data, dict):
            raise UserError(_("AI role entry must be a JSON object."))

        normalized = dict(data)
        alias_map = {
            'group_ids': 'groups',
            'security_groups': 'groups',
            'included_roles': 'implied_roles',
            'implied_role_ids': 'implied_roles',
            'description': 'comment',
        }
        for src, dest in alias_map.items():
            if src in normalized and dest not in normalized:
                normalized[dest] = normalized.pop(src)
            elif src in normalized:
                normalized.pop(src, None)

        if force_name:
            normalized['name'] = force_name
        elif not normalized.get('name'):
            normalized['name'] = _('Generated Role')

        for key in ('groups', 'implied_roles'):
            if key not in normalized or normalized[key] is None:
                normalized[key] = []
            elif not isinstance(normalized[key], list):
                normalized[key] = [normalized[key]]

        if normalized.get('comment') in (False, None, True):
            normalized['comment'] = False

        return normalized

    def _resolve_implied_roles(self, values, exclude_id=None):
        Role = self.env['access.role'].sudo()
        ids = []
        seen = set()
        for value in values or []:
            if not value:
                continue
            if not isinstance(value, str):
                value = str(value)
            value = value.strip()
            if not value:
                continue
            rec = Role.search([('name', '=ilike', value)], limit=1)
            if not rec:
                rec = Role.search([('name', 'ilike', value)], limit=1)
            if rec and rec.id != exclude_id and rec.id not in seen:
                ids.append(rec.id)
                seen.add(rec.id)
        return ids

    def action_generate_role(self):
        self.ensure_one()

        create_new = bool(self.create_new or self.env.context.get('access_role_ai_create'))
        existing_role = False
        if not create_new:
            existing_role = self.role_id
            if not existing_role and self.env.context.get('active_model') == 'access.role':
                active_id = self.env.context.get('active_id')
                if active_id:
                    existing_role = self.env['access.role'].browse(active_id).exists()

        # Suggested name for create; existing name when updating
        role_name = ''
        if existing_role:
            role_name = existing_role.name
        elif self.role_name:
            role_name = self.role_name.strip()

        full_prompt = self._get_schema_instructions(
            role_name, create_new=bool(create_new or not existing_role)
        ) + self.prompt

        text_response = self._call_ai(full_prompt)
        parsed = self._extract_json(text_response)

        roles = parsed.get('roles') if isinstance(parsed, dict) else None
        if roles is None and isinstance(parsed, list):
            roles = parsed
        if not roles:
            if isinstance(parsed, dict) and (
                'groups' in parsed or 'group_ids' in parsed or 'comment' in parsed or 'name' in parsed
            ):
                roles = [parsed]
            else:
                raise UserError(
                    _("AI returned no roles.\n\nRaw Response: %s") % text_response
                )

        # Force existing name only when updating; on create prefer AI name (or suggested).
        force_name = existing_role.name if existing_role else (role_name or None)
        payload = self._normalize_role_payload(roles[0], force_name=force_name)

        importer = self.env['access.import.export'].create({
            'import_active_status': True,
        })
        group_ids = importer._refs(payload.get('groups', []), 'res.groups')
        implied_ids = self._resolve_implied_roles(
            payload.get('implied_roles', []),
            exclude_id=existing_role.id if existing_role else None,
        )

        vals = {
            'name': (payload.get('name') or role_name or _('Generated Role')).strip(),
            'group_ids': [(6, 0, group_ids)],
            'implied_role_ids': [(6, 0, implied_ids)],
            'comment': payload.get('comment') or False,
        }

        try:
            if existing_role:
                vals['name'] = existing_role.name
                existing_role.write(vals)
                role = existing_role
            else:
                # Avoid duplicate empty-looking names when possible
                role = self.env['access.role'].create(vals)
        except UserError:
            raise
        except Exception as e:
            raise UserError(_("Failed to apply AI output to the role: %s") % str(e))

        summary_parts = []
        if role.group_ids:
            summary_parts.append(_("%s groups") % len(role.group_ids))
        if role.implied_role_ids:
            summary_parts.append(_("%s included roles") % len(role.implied_role_ids))
        if role.comment:
            summary_parts.append(_('description'))
        summary = ', '.join(summary_parts) if summary_parts else _('basic settings')

        if existing_role:
            next_action = {'type': 'ir.actions.client', 'tag': 'soft_reload'}
        else:
            next_action = {
                'type': 'ir.actions.act_window',
                'name': _('Role'),
                'res_model': 'access.role',
                'view_mode': 'form',
                'views': [(False, 'form')],
                'res_id': role.id,
                'target': 'current',
            }

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Role Updated') if existing_role else _('Role Created'),
                'message': _('AI applied settings to "%s" (%s).') % (role.name, summary),
                'type': 'success',
                'sticky': False,
                'next': next_action,
            },
        }
