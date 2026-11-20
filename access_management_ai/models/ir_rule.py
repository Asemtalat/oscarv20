# Copyright (C) NexGen Solutions
import logging
from datetime import datetime, time as datetime_time, timedelta

from dateutil.relativedelta import relativedelta
import pytz

from odoo import api, fields, models
from odoo.fields import Domain
from odoo.tools.safe_eval import safe_eval, time

_logger = logging.getLogger(__name__)


class AccessManagementBase(models.AbstractModel):
    """Apply profile record domains through Odoo 20's unified access domain."""
    _inherit = 'base'

    def _access_management_eval_context(self):
        user = self.env.user.with_context({})
        return {
            'user': user,
            'uid': self.env.uid,
            'EU': self.env.uid,  # shortcut alias: Environment User
            'time': time,
            'company_id': self.env.company.id,
            'company_ids': self.env.companies.ids,
        }

    @staticmethod
    def _access_management_date_domain(line, model):
        if not line.date_filter_field or not line.date_filter_period:
            return None
        field = model._fields.get(line.date_filter_field)
        if not field or field.type not in ('date', 'datetime'):
            return None
        today = fields.Date.context_today(model)
        period = line.date_filter_period
        if period == 'today':
            start, end = today, today
        elif period == 'yesterday':
            start = end = today - timedelta(days=1)
        elif period == 'this_week':
            start = today - timedelta(days=today.weekday())
            end = start + timedelta(days=6)
        elif period == 'last_week':
            end = today - timedelta(days=today.weekday() + 1)
            start = end - timedelta(days=6)
        elif period == 'this_month':
            start = today.replace(day=1)
            end = start + relativedelta(months=1, days=-1)
        elif period == 'last_month':
            end = today.replace(day=1) - timedelta(days=1)
            start = end.replace(day=1)
        elif period == 'this_year':
            start = today.replace(month=1, day=1)
            end = today.replace(month=12, day=31)
        elif period == 'last_year':
            start = today.replace(year=today.year - 1, month=1, day=1)
            end = today.replace(year=today.year - 1, month=12, day=31)
        else:
            return None
        next_day = end + timedelta(days=1)
        if field.type == 'datetime':
            tz = pytz.timezone(model.env.user.tz or 'UTC')

            def utc_string(day, at_time):
                local = tz.localize(datetime.combine(day, at_time))
                utc = local.astimezone(pytz.UTC).replace(tzinfo=None)
                return fields.Datetime.to_string(utc)

            start_value = utc_string(start, datetime_time.min)
            end_value = utc_string(next_day, datetime_time.min)
        else:
            start_value = fields.Date.to_string(start)
            end_value = fields.Date.to_string(next_day)
        return [
            (line.date_filter_field, '>=', start_value),
            (line.date_filter_field, '<', end_value),
        ]

    def _access_management_hierarchy_domain(self, line, model):
        if not (line.hierarchy_field and line.hierarchy_user_field and line.hierarchy_mode):
            return None
        parent = model._fields.get(line.hierarchy_field)
        user_field = model._fields.get(line.hierarchy_user_field)
        if not parent or parent.type != 'many2one' or not user_field:
            return None
        if line.hierarchy_field != getattr(model, '_parent_name', None):
            return None
        if user_field.type != 'many2one' or user_field.comodel_name != 'res.users':
            return None
        roots = model.sudo().search([(line.hierarchy_user_field, '=', self.env.uid)]).ids
        if not roots:
            return [('id', '=', 0)]
        operator = 'child_of' if line.hierarchy_mode == 'descendants' else 'parent_of'
        # The hierarchy operator applies to the record id; the configured
        # parent field tells Odoo which tree to traverse.
        return [('id', operator, roots)]

    @api.model
    def _access_domain(self, operation):
        domain = super()._access_domain(operation)

        if self.env.su:
            return domain

        rules = self.env['access.management']._rules_for_user(self.env.uid)
        if not rules:
            return domain

        field_name = 'domain_%s' % operation
        eval_context = self._access_management_eval_context()
        extra = []
        target_model = self
        for line in rules.model_access_ids.filtered(lambda l: l.model_name == self._name):
            if line.warn_mode and operation != 'read':
                continue
            if line.soft_restrict:
                # Soft restrict means the domain only applies if this is the primary model being accessed.
                # If this model is being accessed as a related record (e.g. from many2one read), we skip the domain.
                import inspect
                # We check the call stack. If the primary caller model is different from model_name, skip.
                # Inspect ORM callers, never a client-supplied context flag.
                # A direct access check on an empty recordset is primary too.
                primary_model = self._name
                frame = inspect.currentframe().f_back
                try:
                    while frame:
                        if frame.f_code.co_name in ('_access_domain', 'web_search_read', 'web_read', 'search_read', 'search', 'read'):
                            caller = frame.f_locals.get('self')
                            if isinstance(caller, models.BaseModel):
                                primary_model = caller._name
                        frame = frame.f_back
                finally:
                    del frame
                if primary_model != self._name:
                    continue

            line_domains = []
            expr = line[field_name]
            if expr:
                try:
                    line_domains.append(Domain(safe_eval(expr, eval_context)))
                except Exception:  # noqa: BLE001
                    _logger.warning(
                        "Access Management: invalid %s domain on model %s: %r",
                        field_name, self._name, expr)
                    # Fail securely to prevent exposing confidential data
                    line_domains.append(Domain([('id', '=', 0)]))
            date_domain = self._access_management_date_domain(line, target_model)
            if date_domain:
                line_domains.append(Domain(date_domain))
            hierarchy_domain = self._access_management_hierarchy_domain(line, target_model)
            if hierarchy_domain:
                line_domains.append(Domain(hierarchy_domain))
            
            if line_domains:
                extra.append(Domain.AND(line_domains))
        if not extra:
            return domain
        
        # Multiple rules from different profiles for the same model should be ORed 
        # to prevent blocking legitimate users (similar to group-level ir.rule logic)
        extra_domain = Domain.OR(extra)
        return Domain.AND([domain, extra_domain]).optimize(self)
