# Copyright (C) NexGen Solutions
from odoo import api, models
from odoo.fields import Domain

# For view-only users we still let the web client write its own technical
# records (preferences, bus, mail, filters, ...) so the UI keeps working;
# only business data writes are blocked.
_READONLY_ALLOWED_PREFIXES = ('ir.', 'bus.', 'mail.', 'web_', 'res.users', 'res.lang', 'res.config')


class AccessManagementBase(models.AbstractModel):
    """Integrate profile CRUD restrictions with Odoo 20's access API.

    Odoo 20 replaced ``ir.model.access`` with ``ir.access`` and made model
    access decisions through :meth:`base._access_domain`.  Extending the old
    model silently stopped enforcing profile CRUD settings, so enforcement now
    happens at the same model-level entry point as Odoo's native permissions.
    """
    _inherit = 'base'

    @api.model
    def _access_management_denied_models(self, operation):
        """ Set of model names the current user may NOT ``mode`` because of an
        access management rule (only create/write/unlink are enforced here). """
        if operation not in ('create', 'write', 'unlink') or self.env.su:
            return frozenset()

        denied = set()
        rules = self.env['access.management']._rules_for_user(self.env.uid)
        perm_field = 'perm_%s' % operation
        for line in rules.model_access_ids:
            if not line[perm_field] and not line.warn_mode:
                denied.add(line.model_name)

        # View-only user: block writes to business models.
        user = self.env.user
        is_readonly = user.sudo().access_read_only or any(r.readonly for r in rules)
        if is_readonly:
            for model_name in self.env.registry.models:
                if not model_name.startswith(_READONLY_ALLOWED_PREFIXES):
                    denied.add(model_name)

        return frozenset(denied)

    @api.model
    def _access_domain(self, operation):
        domain = super()._access_domain(operation)
        if self.env.su or self._name not in self._access_management_denied_models(operation):
            return domain
        return Domain.FALSE
