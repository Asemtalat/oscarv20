# Copyright (C) NexGen Solutions
from odoo import _, api, models
from odoo.exceptions import AccessError


class IrFilters(models.Model):
    _inherit = 'ir.filters'

    @api.model
    def get_filters(self, model, action_id=None, embedded_action_id=None, embedded_parent_res_id=None):
        result = super().get_filters(model, action_id, embedded_action_id, embedded_parent_res_id)
        if self.env.su:
            return result
        rules = self.env['access.management']._rules_for_user(self.env.uid)
        hide = any(r.global_hide_favorites for r in rules) or any(
            line.model_name == model and line.hide_favorites
            for line in rules.model_access_ids
        )
        return [] if hide else result

    def unlink(self):
        if not self.env.su and any(
            r.global_hide_filter_delete
            for r in self.env['access.management']._rules_for_user(self.env.uid)
        ):
            raise AccessError(_("Deleting saved filters is disabled for your user."))
        return super().unlink()
