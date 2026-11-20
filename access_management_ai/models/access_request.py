# -*- coding: utf-8 -*-
# Copyright (C) NexGen Solutions
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError
import datetime

class AccessRequest(models.Model):
    _name = 'access.request'
    _description = 'Access Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(string='Reference', required=True, copy=False, readonly=True, default=lambda self: _('New'))
    user_id = fields.Many2one('res.users', string='Requested By', required=True, default=lambda self: self.env.user, tracking=True, domain=[('share', '=', False)])
    role_id = fields.Many2one('access.role', string='Requested Role', tracking=True)
    profile_id = fields.Many2one('access.management', string='Requested Profile', tracking=True)
    
    request_reason = fields.Text(string='Reason for Request', required=True, tracking=True)
    date_from = fields.Date(string='Requested From', default=fields.Date.context_today)
    date_to = fields.Date(string='Requested Until')
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('expired', 'Expired'),
        ('revoked', 'Revoked')
    ], string='Status', default='draft', tracking=True, required=True)
    
    approver_id = fields.Many2one('res.users', string='Approved/Rejected By', tracking=True, domain=[('share', '=', False)])
    rejection_reason = fields.Text(string='Rejection Reason', tracking=True)
    granted_role_line_id = fields.Many2one(
        'access.role.line', readonly=True, copy=False, ondelete='set null',
        groups='access_management_ai.group_access_manager')
    profile_grant_owned = fields.Boolean(
        readonly=True, copy=False, groups='access_management_ai.group_access_manager',
        help='Whether this request added the direct profile assignment.')

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        from odoo.exceptions import ValidationError
        for rec in self:
            if rec.date_from and rec.date_to and rec.date_to < rec.date_from:
                raise ValidationError("Invalid validity period: 'Requested Until' date must be greater than or equal to 'Requested From' date.")

    @api.constrains('role_id', 'profile_id')
    def _check_role_or_profile(self):
        from odoo.exceptions import ValidationError
        for rec in self:
            if bool(rec.role_id) == bool(rec.profile_id):
                raise ValidationError("Select exactly one Requested Role or Requested Profile.")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not self._am_is_manager():
                if vals.get('user_id', self.env.uid) != self.env.uid or vals.get('state', 'draft') != 'draft' or vals.get('approver_id'):
                    raise AccessError(_("You may only create your own draft requests."))
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('access.request') or _('New')
        return super().create(vals_list)

    def _am_is_manager(self):
        return self.env.su or self.env.user.has_group('access_management_ai.group_access_manager')

    def _am_check_manager(self):
        if not self._am_is_manager():
            raise AccessError(_("Only Access Administrators can approve, reject or revoke requests."))

    def write(self, vals):
        grant_fields = {'user_id', 'role_id', 'profile_id', 'date_from', 'date_to'}
        if not self._am_is_manager():
            editable = {'role_id', 'profile_id', 'request_reason', 'date_from', 'date_to'}
            if set(vals) - editable or any(r.user_id != self.env.user or r.state != 'draft' for r in self):
                raise AccessError(_("You may only edit your own draft request details."))
        if grant_fields.intersection(vals) and any(req.state != 'draft' for req in self):
            raise UserError(_("The user, role/profile and dates cannot change after a request is submitted. Create a new request instead."))
        return super().write(vals)

    def unlink(self):
        if any(req.state == 'approved' for req in self):
            raise UserError(_("Revoke approved requests before deleting them."))
        return super().unlink()

    def _grant_profile_access(self, today=None):
        today = today or fields.Date.context_today(self)
        for req in self:
            if (req.state != 'approved' or not req.profile_id
                    or (req.date_from and req.date_from > today)
                    or (req.date_to and req.date_to < today)):
                continue
            if req.user_id not in req.profile_id.user_ids:
                req.profile_id.with_context(audit_reason=f"Approved Request: {req.name}").write({
                    'user_ids': [(4, req.user_id.id)],
                })
                req.profile_grant_owned = True

    def _revoke_granted_access(self, reason):
        today = fields.Date.context_today(self)
        for req in self:
            line = req.granted_role_line_id
            if line and line.user_id == req.user_id and line.role_id == req.role_id:
                line.with_context(audit_reason=reason).unlink()
            if not req.profile_grant_owned:
                continue
            # A shared grant stays until the final currently valid request ends.
            successor = self.search([
                ('id', '!=', req.id), ('state', '=', 'approved'),
                ('user_id', '=', req.user_id.id), ('profile_id', '=', req.profile_id.id),
                '|', ('date_from', '=', False), ('date_from', '<=', today),
                '|', ('date_to', '=', False), ('date_to', '>=', today),
            ], limit=1)
            if successor:
                successor.profile_grant_owned = True
            else:
                req.profile_id.with_context(audit_reason=reason).write({
                    'user_ids': [(3, req.user_id.id)],
                })
            req.profile_grant_owned = False

    def action_submit(self):
        self.check_access('write')
        for req in self:
            if req.state != 'draft':
                raise UserError(_("Only draft requests can be submitted."))
            # The transition is private to this checked workflow, never a
            # context flag a caller could use to bypass write protection.
            req.sudo().write({'state': 'submitted'})
            req = req.sudo()
            # Create activity for admin and send emails
            users = self.env.ref('access_management_ai.group_access_manager').user_ids
            
            # 1. Notify Requester
            req.message_post(body=_("Your access request has been submitted successfully."))
            requester_template = self.env.ref('access_management_ai.mail_template_access_submitted_requester', raise_if_not_found=False)
            if requester_template:
                requester_template.send_mail(req.id, force_send=True)
                
            # 2. Notify Approvers and create activities
            approver_template = self.env.ref('access_management_ai.mail_template_access_submitted_approver', raise_if_not_found=False)
            for user in users:
                req.activity_schedule(
                    'mail.mail_activity_data_todo',
                    user_id=user.id,
                    note=f"Review access request {req.name} from {req.user_id.name}"
                )
                if approver_template and user.email_formatted:
                    approver_template.with_context(approver_email=user.email_formatted).send_mail(req.id, force_send=True)
        return True

    def action_approve(self):
        self._am_check_manager()
        for req in self:
            if req.state != 'submitted':
                raise UserError(_("Only submitted requests can be approved."))
            if req.role_id and self.env['access.role.line'].search_count([
                    ('role_id', '=', req.role_id.id), ('user_id', '=', req.user_id.id)]):
                raise UserError(_("This user already has an assignment for the requested role. Update that assignment instead."))
            req.state = 'approved'
            req.approver_id = self.env.user.id
            
            # Grant access
            if req.role_id:
                req.granted_role_line_id = self.env['access.role.line'].create({
                    'role_id': req.role_id.id,
                    'user_id': req.user_id.id,
                    'date_from': req.date_from,
                    'date_to': req.date_to,
                    'audit_reason': f"Approved Request: {req.name}"
                })
            req._grant_profile_access()
            
            # Notify user
            req.message_post(body=_("Your access request has been approved."))
            template = self.env.ref('access_management_ai.mail_template_access_approved', raise_if_not_found=False)
            if template:
                template.send_mail(req.id, force_send=True)
                
            # Clear activities
            req.activity_unlink(['mail.mail_activity_data_todo'])
        return True

    def action_reject(self):
        self._am_check_manager()
        self.ensure_one()
        return {
            'name': _('Reject Access Request'),
            'type': 'ir.actions.act_window',
            'res_model': 'access.request.reject',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_request_id': self.id}
        }

    def action_revoke(self):
        self._am_check_manager()
        for req in self:
            if req.state != 'approved':
                raise UserError(_("Only approved requests can be revoked."))
            req.state = 'revoked'
            
            req._revoke_granted_access(f"Revoked via Request: {req.name}")
                
            # Notify user
            req.message_post(body=_("Your access has been revoked."))
            template = self.env.ref('access_management_ai.mail_template_access_revoked', raise_if_not_found=False)
            if template:
                template.send_mail(req.id, force_send=True)
        return True

    @api.model
    def _cron_check_expiring_access(self):
        today = fields.Date.context_today(self)
        self.search([('state', '=', 'approved'), ('profile_id', '!=', False)])._grant_profile_access(today)
        
        # 1. Reminders: Find active requests that expire in exactly 2 days, 1 day, or today
        two_days = today + datetime.timedelta(days=2)
        one_day = today + datetime.timedelta(days=1)
        
        reminders = self.search([
            ('state', '=', 'approved'), 
            ('date_to', 'in', [two_days, one_day, today])
        ])
        
        reminder_template = self.env.ref('access_management_ai.mail_template_access_reminder', raise_if_not_found=False)
        for req in reminders:
            days_left = (req.date_to - today).days
            if days_left == 0:
                msg = _("Your access will expire today.")
            elif days_left == 1:
                msg = _("Your access will expire in 1 day.")
            else:
                msg = _("Your access will expire in 2 days.")
                
            req.message_post(body=msg)
            if reminder_template:
                reminder_template.send_mail(req.id, force_send=True)
                
        # 2. Expirations: Find active requests that have expired yesterday or earlier
        expired = self.search([('state', '=', 'approved'), ('date_to', '<', today)])
        for req in expired:
            req.state = 'expired'
            req._revoke_granted_access(f"Expired Request: {req.name}")
            req.message_post(body=_("Your access has expired."))
            expired_template = self.env.ref('access_management_ai.mail_template_access_expired', raise_if_not_found=False)
            if expired_template:
                expired_template.send_mail(req.id, force_send=True)

class AccessRequestReject(models.TransientModel):
    _name = 'access.request.reject'
    _description = 'Access Request Reject Wizard'

    request_id = fields.Many2one('access.request', required=True)
    reason = fields.Text('Rejection Reason', required=True)

    def action_reject(self):
        self.ensure_one()
        self.request_id._am_check_manager()
        if self.request_id.state != 'submitted':
            raise UserError(_("Only submitted requests can be rejected."))
        self.request_id.state = 'rejected'
        self.request_id.approver_id = self.env.user.id
        self.request_id.rejection_reason = self.reason
        
        # Notify user
        self.request_id.message_post(body=_("Your access request was rejected. Reason: %s", self.reason))
        template = self.env.ref('access_management_ai.mail_template_access_rejected', raise_if_not_found=False)
        if template:
            template.send_mail(self.request_id.id, force_send=True)
            
        self.request_id.activity_unlink(['mail.mail_activity_data_todo'])
