# -*- coding: utf-8 -*-
# Copyright (C) NexGen Solutions
from odoo import api, fields, models

class AccessAuditLog(models.Model):
    _name = 'access.audit.log'
    _description = 'Access Audit Log'
    _order = 'create_date desc'

    action = fields.Selection([
        ('grant', 'Granted Access'),
        ('revoke', 'Revoked Access'),
        ('modify', 'Modified Access'),
        ('workflow', 'Workflow Action'),
        ('failed', 'Failed Attempt')
    ], string='Action', required=True)
    
    admin_user_id = fields.Many2one('res.users', string='Changed By', default=lambda self: self.env.user, index=True, domain=[('share', '=', False)])
    target_user_id = fields.Many2one('res.users', string='Target User', index=True, domain=[('share', '=', False)])
    
    model_name = fields.Char(string='Record Type')
    record_name = fields.Char(string='Record Name')
    
    previous_value = fields.Text(string='Previous Value')
    new_value = fields.Text(string='New Value')
    reason = fields.Char(string='Reason')
    
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)

    @api.depends('action', 'record_name')
    def _compute_display_name(self):
        """Odoo 20 uses ``display_name`` instead of the removed name_get API."""
        labels = dict(self._fields['action'].selection)
        for log in self:
            log.display_name = f"{labels.get(log.action, '')} - {log.record_name or ''}"
