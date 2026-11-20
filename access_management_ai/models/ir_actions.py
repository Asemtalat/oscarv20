# Copyright (C) NexGen Solutions
from odoo import models, api, SUPERUSER_ID


_ACTION_RULE_FIELDS = {
    'ir.actions.act_window': 'action_ids',
    'ir.actions.server': 'server_action_ids',
    'ir.actions.client': 'client_action_ids',
    'ir.actions.act_url': 'url_action_ids',
    'ir.actions.report': 'report_ids',
}


class IrActionsActions(models.Model):
    _inherit = 'ir.actions.actions'

    def _access_management_hidden_ids(self, model_name=None):
        if self.env.uid == SUPERUSER_ID:
            return set()
        field_name = _ACTION_RULE_FIELDS.get(self._name)
        if not field_name:
            return set()
        return self.env['access.management']._hidden_action_ids_for_user(
            self.env.uid, model_name=model_name, action_field=field_name,
        )

    def read(self, fields=None, load='_classic_read'):
        result = super().read(fields, load)
        if fields and 'binding_view_types' in fields:
            return result
        hidden = self._access_management_hidden_ids()
        return [action for action in result if action.get('id') not in hidden]

    @api.model
    def get_bindings(self, model_name):
        res = super().get_bindings(model_name)
        if self.env.uid == SUPERUSER_ID:
            return res

        hidden_ids = self.env['access.management']._hidden_action_ids_for_user(
            self.env.uid, model_name=model_name,
        )
        if not hidden_ids:
            return res

        for action_type, actions in res.items():
            res[action_type] = [a for a in actions if a.get('id') not in hidden_ids]

        return res

    def _get_action_dict(self):
        hidden = self._access_management_hidden_ids()
        if self.id in hidden:
            from odoo.exceptions import AccessError
            from odoo import _
            raise AccessError(_("You are not allowed to access this action."))
        return super()._get_action_dict()


class IrActionsActWindow(models.Model):
    _inherit = 'ir.actions.act_window'

    def _access_management_filter_action_dict(self, action, rules):
        res_model = action.get('res_model')
        if not res_model:
            return
        hidden = set()
        for line in rules.model_access_ids:
            if line.model_name != res_model:
                continue
            hidden |= line._hidden_view_types()
        if not hidden:
            return
        if action.get('view_mode'):
            modes = [m for m in action['view_mode'].split(',') if m not in hidden]
            action['view_mode'] = ','.join(modes)
        if action.get('views'):
            action['views'] = [v for v in action['views'] if v[1] not in hidden]

    def read(self, fields=None, load='_classic_read'):
        result = super().read(fields, load)
        # actions are loaded with sudo, so filter on the real user (env.uid),
        # not the su flag; skip only for the technical superuser.
        if self.env.uid == SUPERUSER_ID:
            return result
        rules = self.env['access.management']._rules_for_user(self.env.uid)
        if not rules:
            return result
        
        for action in result:
            self._access_management_filter_action_dict(action, rules)
        return result

    def _get_action_dict(self):
        result = super()._get_action_dict()
        if self.env.uid == SUPERUSER_ID:
            return result
        rules = self.env['access.management']._rules_for_user(self.env.uid)
        if not rules:
            return result
        self._access_management_filter_action_dict(result, rules)
        
        if 'view_mode' in result and not result.get('view_mode'):
            from odoo.exceptions import AccessError
            from odoo import _
            raise AccessError(_("You do not have access to any views for this action."))
        
        return result
