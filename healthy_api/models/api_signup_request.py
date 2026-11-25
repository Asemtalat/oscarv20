# -*- coding: utf-8 -*-

from odoo import _, fields, models
from odoo.exceptions import UserError


class ApiSignupRequest(models.Model):
    _name = 'api.signup.request'
    _description = 'API Signup Approval Request'
    _order = 'create_date desc, id desc'

    name = fields.Char(required=True)
    email = fields.Char(required=True, index=True)
    mobile = fields.Char(required=True, index=True)
    password = fields.Char()
    state = fields.Selection([
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], required=True, default='pending', index=True)
    reviewed_by_id = fields.Many2one('res.users', string='Reviewed By')
    reviewed_at = fields.Datetime()
    reject_reason = fields.Char(string='Reject Reason')
    created_user_id = fields.Many2one('res.users', string='Created User', readonly=True)

    def _check_admin_access(self):
        if not self.env.user.has_group('healthy_api.group_api_admin'):
            raise UserError(_('Only API admins can review signup requests.'))

    def approve_and_create_user(self):
        self.ensure_one()
        self._check_admin_access()
        if self.state != 'pending':
            raise UserError(_('Signup request is not pending.'))

        Users = self.env['res.users'].sudo().with_context(
            no_reset_password=True,
            mail_create_nolog=True,
            mail_create_nosubscribe=True,
            tracking_disable=True,
        )
        if Users.search_count(['|', ('login', '=', self.email), ('partner_id.mobile', '=', self.mobile)]):
            self.sudo().write({
                'state': 'rejected',
                'reviewed_by_id': self.env.user.id,
                'reviewed_at': fields.Datetime.now(),
                'reject_reason': 'Email/mobile already used by an existing user',
            })
            raise UserError(_('Email/mobile already in use.'))

        created_user = Users.create({
            'name': self.name,
            'login': self.email,
            'email': self.email,
            'password': self.password,
            'active': True,
            'api_user_state': 'approved',
        })
        if created_user.partner_id:
            created_user.partner_id.sudo().write({'mobile': self.mobile})

        self.sudo().write({
            'state': 'approved',
            'reviewed_by_id': self.env.user.id,
            'reviewed_at': fields.Datetime.now(),
            'created_user_id': created_user.id,
            'password': False,
        })
        return created_user

    def action_approve(self):
        for request in self:
            request.approve_and_create_user()
        return True

    def action_reject(self):
        self._check_admin_access()
        now = fields.Datetime.now()
        for request in self:
            if request.state != 'pending':
                raise UserError(_('Only pending signup requests can be rejected.'))
            request.sudo().write({
                'state': 'rejected',
                'reviewed_by_id': self.env.user.id,
                'reviewed_at': now,
            })
        return True
