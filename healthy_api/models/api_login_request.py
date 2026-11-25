# -*- coding: utf-8 -*-

from odoo import _, fields, models
from odoo.exceptions import UserError


class ApiLoginRequest(models.Model):
    _name = 'api.login.request'
    _description = 'API Login Approval Request'
    _order = 'create_date desc, id desc'
    _rec_name = 'user_id'
    user_id = fields.Many2one('res.users', required=True, ondelete='cascade', index=True)
    supervisor_id = fields.Many2one('res.users', string='Supervisor', index=True)
    state = fields.Selection([
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], required=True, default='pending', index=True)
    requested_at = fields.Datetime(default=fields.Datetime.now, required=True)
    reviewed_at = fields.Datetime()
    reviewed_by_id = fields.Many2one('res.users', string='Reviewed By')
    reject_reason = fields.Char(string='Reject Reason')
    request_date = fields.Date(default=fields.Date.context_today, required=True, index=True)

    def _check_can_review(self):
        for record in self:
            user = self.env.user
            if user.has_group('healthy_api.group_api_admin'):
                continue
            if user.has_group('healthy_api.group_api_supervisor') and record.supervisor_id == user:
                continue
            raise UserError(_('You are not allowed to review this login request.'))

    def action_approve(self):
        self._check_can_review()
        self.write({
            'state': 'approved',
            'reviewed_at': fields.Datetime.now(),
            'reviewed_by_id': self.env.user.id,
            'reject_reason': False,
        })
        return True

    def action_reject(self):
        self._check_can_review()
        self.write({
            'state': 'rejected',
            'reviewed_at': fields.Datetime.now(),
            'reviewed_by_id': self.env.user.id,
        })
        return True
