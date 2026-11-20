# Copyright (C) NexGen Solutions
from odoo import api, models


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    @api.model
    def _access_management_hidden_menu_ids(self):
        """ Menu ids hidden for the current user, including whole sub-trees. """
        rules = self.env['access.management']._rules_for_user(self.env.uid)
        menus = rules.menu_ids
        if self.env['ir.module.module']._access_management_module_change_blocked():
            for xmlid in ('base.menu_view_base_module_update',
                          'base_import_module.menu_view_base_module_import'):
                menu = self.env.ref(xmlid, raise_if_not_found=False)
                if menu:
                    menus |= menu.sudo()
        if not menus:
            return frozenset()
        # hide the selected menus together with all their descendants
        hidden = self.sudo().search([('id', 'child_of', menus.ids)])
        return frozenset(hidden.ids)

    @api.model
    def _visible_menu_ids(self, debug=False):
        visible = super()._visible_menu_ids(debug)
        hidden = self._access_management_hidden_menu_ids()
        if hidden:
            return frozenset(visible) - hidden
        return visible

    @api.model
    def _access_management_refresh_menu_cache(self):
        # Native menu payloads are cached independently of the current time
        # and selected companies. Profiles with menu restrictions must be
        # evaluated again when a client reloads its menus.
        profiles = self.env['access.management'].with_context(
            allowed_company_ids=self.env.user.sudo().company_ids.ids)
        rules = profiles.sudo().browse(profiles._rule_ids_for_user(self.env.uid))
        if rules.menu_ids or any(r.readonly or r.block_module_management for r in rules) or self.env.user.sudo().access_read_only:
            self.env.transaction.invalidate_ormcache()

    @api.model
    def load_menus(self, debug):
        self._access_management_refresh_menu_cache()
        return super().load_menus(debug)

    @api.model
    def load_menus_root(self):
        self._access_management_refresh_menu_cache()
        return super().load_menus_root()
