# Copyright (C) NexGen Solutions
"""Server-side export enforcement."""
from odoo import _, api, models
from odoo.exceptions import AccessError


class BaseExport(models.AbstractModel):
    _inherit = 'base'

    @api.model
    def _access_management_export_config(self):
        if self.env.su:
            return False, set()
        rules = self.env['access.management']._rules_for_user(self.env.uid)
        model_lines = rules.model_access_ids.filtered(lambda line: line.model_name == self._name)
        blocked_fields = {
            line.field_name
            for line in rules.field_access_ids
            if line.model_name == self._name and (line.is_invisible or line.restrict_export)
        }
        disabled = any(not line.allow_export for line in model_lines)
        disabled = disabled or any(rule.global_hide_export for rule in rules)
        disabled = disabled or self.env.user.sudo().access_read_only or any(rule.readonly for rule in rules)
        return disabled, blocked_fields

    @api.model
    def fields_get(self, allfields=None, attributes=None):
        res = super().fields_get(allfields=allfields, attributes=attributes)
        disabled, blocked_fields = self._access_management_export_config()
        if disabled:
            for field in res:
                res[field]['exportable'] = False
        elif blocked_fields:
            for field in blocked_fields:
                if field in res:
                    res[field]['exportable'] = False
        return res

    @api.model
    def _access_management_export_path_blocked(self, path):
        model = self
        for part in path:
            disabled, blocked_fields = model._access_management_export_config()
            name = part.split(':', 1)[0].split('@', 1)[0]
            if name != '.id':
                name = name.split('.', 1)[0]
            if disabled or name in blocked_fields:
                return True
            field = model._fields.get(name)
            if not field or not field.relational or not field.comodel_name:
                break
            model = self.env[field.comodel_name]
        return False

    def _export_rows(self, fields, *, _is_toplevel_call=True):
        # Odoo recursively calls _export_rows, not export_data, for related
        # records. Check every path and recursive call, including translations.
        blocked = [i for i, path in enumerate(fields)
                   if path and self._access_management_export_path_blocked(path)]
        rows = super()._export_rows(fields, _is_toplevel_call=_is_toplevel_call)
        for row in rows:
            for index in blocked:
                row[index] = ''
        return rows

    def export_data(self, fields_to_export):
        disabled, _blocked_fields = self._access_management_export_config()
        if disabled:
            raise AccessError(_('Export is disabled for this model and user.'))
            
        # ``raw_data`` was removed from the public ORM API in Odoo 20.
        return super().export_data(fields_to_export)
