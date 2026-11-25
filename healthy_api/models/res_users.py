# -*- coding: utf-8 -*-
"""
Extensions to the ``res.users`` model to support API token authentication.

Each user gets a unique token stored in the ``api_token`` field. This token
is automatically generated using Python's ``secrets`` module. The token
can be used by external clients to authenticate against the REST API
endpoints implemented in ``healthy_api.controllers.api``. The module
provides a helper method ``get_user_from_token`` for retrieving a user
record from a given token.
"""

import secrets
from odoo import api, fields, models
from datetime import date
import hashlib


class ResUsers(models.Model):
    _inherit = 'res.users'

    API_GROUP_XMLIDS = {
        'delegate': 'healthy_api.group_api_delegate',
        'supervisor': 'healthy_api.group_api_supervisor',
        'warehouse': 'healthy_api.group_api_warehouse',
        'admin': 'healthy_api.group_api_admin',
    }

    api_token = fields.Char(
        string='API Token',
        copy=False,
        readonly=True,
        default=lambda self: secrets.token_urlsafe(32),
        help='Token used for authenticating API requests.',
    )
    api_user_state = fields.Char(
        string='User State',
        copy=False,
        readonly=True,
    )
    # New fields for per‑day tokens
    daily_api_token = fields.Char(
        string='Daily API Token',
        copy=False,
        readonly=True,
        help='Token valid only for the current day, generated on login.',
    )
    daily_token_date = fields.Date(
        string='Daily Token Date',
        readonly=True,
        help='Date for which the daily_api_token is valid.',
    )
    supervisor_id = fields.Many2one(
        'res.users',
        string='Supervisor',
        domain="[('id', '!=', id)]",
        help='Direct supervisor used to scope API access for delegates.',
    )
    subordinate_ids = fields.One2many('res.users', 'supervisor_id', string='Subordinates')
    area_name = fields.Char(string='Area')
    api_rule_ids = fields.Many2many(
        'api.rules',
        'res_users_api_rules_rel',
        'user_id',
        'rule_id',
        string='API Rules'
    )

    @api.model
    def get_user_from_token(self, token):
        """Return the user associated with the given API token."""
        return self.sudo().search([('api_token', '=', token)], limit=1)

    def get_daily_token(self):
        """
        Compute a daily token for the user based on the static api_token and
        the current date. The daily token changes every day (UTC) and is
        derived by hashing the static token with the date string YYYYMMDD.

        :return: string containing the daily token
        """
        self.ensure_one()
        date_str = date.today().strftime('%Y%m%d')
        # Combine static token and date, then compute SHA256
        data = (self.api_token or '') + date_str
        return hashlib.sha256(data.encode('utf-8')).hexdigest()

    def generate_daily_api_token(self):
        """
        Generate or retrieve the per‑day token for the user.

        If the ``daily_api_token`` is missing or the stored date is not
        today, this method will generate a new secure token and update
        ``daily_api_token`` and ``daily_token_date`` accordingly. It returns
        the token value which can be used by clients for authentication for
        the remainder of the day.

        :return: string containing the daily API token
        """
        self.ensure_one()
        today = fields.Date.context_today(self)
        # If no token or date mismatch, regenerate
        if not self.daily_api_token or self.daily_token_date != today:
            self.daily_api_token = secrets.token_urlsafe(32)
            self.daily_token_date = today
        return self.daily_api_token

    def _has_api_group(self, key):
        self.ensure_one()
        group_xmlid = self.API_GROUP_XMLIDS[key]
        return self.has_group(group_xmlid)

    def has_api_access(self):
        self.ensure_one()
        if any(self._has_api_group(key) for key in self.API_GROUP_XMLIDS):
            return True
        return bool(self.api_rule_ids)

    def is_api_delegate(self):
        self.ensure_one()
        return self._has_api_group('delegate')

    def is_api_supervisor(self):
        self.ensure_one()
        return self._has_api_group('supervisor')

    def is_api_warehouse(self):
        self.ensure_one()
        return self._has_api_group('warehouse')

    def is_api_admin(self):
        self.ensure_one()
        return self._has_api_group('admin')

    def api_role_labels(self):
        self.ensure_one()
        labels = []
        if self.is_api_delegate():
            labels.append('مندوب')
        if self.is_api_supervisor():
            labels.append('مشرف')
        if self.is_api_warehouse():
            labels.append('مخزن')
        if self.is_api_admin():
            labels.append('مسئول')
        return labels
