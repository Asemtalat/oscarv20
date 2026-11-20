# Copyright (C) NexGen Solutions
from odoo import _, api, models
from odoo.exceptions import AccessError


class IrModuleModule(models.Model):
    _inherit = 'ir.module.module'

    @api.model
    def _access_management_module_change_blocked(self):
        if self.env.is_superuser():
            return False
        rules = self.env['access.management']._rules_for_user(self.env.uid)
        return self.env.user.sudo().access_read_only or any(
            rule.readonly or rule.block_module_management for rule in rules)

    def _access_management_module_change_allowed(self):
        if self._access_management_module_change_blocked():
            raise AccessError(_('You are not allowed to install, update, or uninstall modules.'))
        return True

    @classmethod
    def _access_management_guard_values(cls, env):
        env['ir.module.module']._access_management_module_change_allowed()

    @api.model_create_multi
    def create(self, vals_list):
        self._access_management_guard_values(self.env)
        return super().create(vals_list)

    def write(self, vals):
        self._access_management_guard_values(self.env)
        return super().write(vals)

    def unlink(self):
        self._access_management_guard_values(self.env)
        return super().unlink()

    def button_immediate_install(self):
        self._access_management_module_change_allowed()
        return super().button_immediate_install()

    def button_immediate_upgrade(self):
        self._access_management_module_change_allowed()
        return super().button_immediate_upgrade()

    def button_immediate_uninstall(self):
        self._access_management_module_change_allowed()
        return super().button_immediate_uninstall()

    def button_install(self):
        self._access_management_module_change_allowed()
        return super().button_install()

    def button_upgrade(self):
        self._access_management_module_change_allowed()
        return super().button_upgrade()

    def button_uninstall(self):
        self._access_management_module_change_allowed()
        return super().button_uninstall()

    def button_uninstall_wizard(self):
        self._access_management_module_change_allowed()
        return super().button_uninstall_wizard()

    def module_uninstall(self):
        self._access_management_module_change_allowed()
        return super().module_uninstall()

    def button_immediate_install_app(self):
        self._access_management_module_change_allowed()
        return super().button_immediate_install_app()

    def update_list(self):
        self._access_management_module_change_allowed()
        return super().update_list()

    def _import_zipfile(self, *args, **kwargs):
        # The importer elevates its environment before writing module data.
        # Enforce the caller's profile before that elevation (wizard and HTTP).
        self._access_management_module_change_allowed()
        return super()._import_zipfile(*args, **kwargs)
