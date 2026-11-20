# Copyright (C) NexGen Solutions
import json

from odoo import _, fields, models
from odoo.exceptions import UserError
from odoo.tools import BinaryBytes


class AccessManagementTransfer(models.TransientModel):
    _name = 'access.management.transfer'
    _description = 'Access Profiles Import/Export'

    profile_ids = fields.Many2many('access.management', string='Profiles to Export')
    export_file = fields.Binary(string='Export File', readonly=True, attachment=False)
    export_filename = fields.Char(string='Export Filename', readonly=True)
    import_file = fields.Binary(string='Import File')
    import_filename = fields.Char(string='Import Filename')

    def _serialize(self, profiles):
        # Reuse the main Import/Export serializer for a complete field set.
        exporter = self.env['access.import.export']
        return [exporter._export_profile(p) for p in profiles]

    def action_export(self):
        self.ensure_one()
        profiles = self.profile_ids or self.env['access.management'].search([])
        payload = json.dumps({'version': 2, 'profiles': self._serialize(profiles)}, indent=2)
        self.export_file = BinaryBytes(payload.encode(), filename='access_profiles.json')
        self.export_filename = 'access_profiles.json'

        self.env['access.audit.log'].create({
            'action': 'workflow',
            'model_name': 'Profile Export Wizard',
            'record_name': 'AccessManagementTransfer',
            'new_value': f"Exported {len(profiles)} profiles",
            'reason': 'Profile Export',
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_import(self):
        self.ensure_one()
        if not self.import_file:
            raise UserError(_("Please upload a JSON export file first."))
        try:
            payload = json.loads(self.import_file.content.decode())
        except Exception as e:  # noqa: BLE001
            raise UserError(_("Invalid file: %s", e))

        # Support both transfer wrapper format and flat list from Import/Export.
        if isinstance(payload, list):
            profiles_data = payload
        elif isinstance(payload, dict):
            profiles_data = payload.get('profiles', [])
        else:
            raise UserError(_("The JSON file must contain a list of profiles."))
        if not isinstance(profiles_data, list):
            raise UserError(_("The profiles value must be a list."))

        # Normalize legacy transfer keys to Import/Export format.
        normalized = []
        for entry in profiles_data:
            if not isinstance(entry, dict):
                continue
            profile = dict(entry)
            if 'model_access_ids' not in profile and 'models' in profile:
                profile['model_access_ids'] = [
                    dict(m, model_name=m.get('model_name') or m.get('model'))
                    for m in (profile.get('models') or [])
                    if isinstance(m, dict)
                ]
            if 'field_access_ids' not in profile and 'fields' in profile:
                profile['field_access_ids'] = [
                    dict(
                        f,
                        model_name=f.get('model_name') or f.get('model'),
                        field_name=f.get('field_name') or f.get('field'),
                    )
                    for f in (profile.get('fields') or [])
                    if isinstance(f, dict)
                ]
            if 'element_access_ids' not in profile and 'elements' in profile:
                profile['element_access_ids'] = [
                    dict(e, model_name=e.get('model_name') or e.get('model'))
                    for e in (profile.get('elements') or [])
                    if isinstance(e, dict)
                ]
            if 'global_element_ids' not in profile and 'global_elements' in profile:
                profile['global_element_ids'] = [
                    dict(e, model_name=e.get('model_name') or e.get('model'))
                    for e in (profile.get('global_elements') or [])
                    if isinstance(e, dict)
                ]
            normalized.append(profile)

        importer = self.env['access.import.export'].create({
            'action': 'import',
            'import_active_status': True,
        })
        created_ids, _import_log = importer._process_json_profiles(normalized)

        self.env['access.audit.log'].create({
            'action': 'workflow',
            'model_name': 'Profile Import Wizard',
            'record_name': 'AccessManagementTransfer',
            'new_value': f"Imported {len(created_ids)} profiles",
            'reason': 'Profile Import',
        })

        return {
            'type': 'ir.actions.act_window',
            'name': _('Imported Profiles'),
            'res_model': 'access.management',
            'view_mode': 'list,form',
            'domain': [('id', 'in', created_ids)],
        }
