# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta
from markupsafe import Markup
from datetime import timedelta

from odoo import models, fields, api


class DocumentType(models.Model):
    _name = 'documents.document.type'
    _description = 'DocumentType'

    name = fields.Char(required=1)
    


class Documents(models.Model):
    _inherit = 'documents.document'

    document_type_id = fields.Many2one('documents.document.type')
    exp_date = fields.Date('Date of expiration')
    description = fields.Text('Notes/Comment')
    state = fields.Selection(selection=[
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('issue', 'Issue'),
    ], default='draft')

    @api.model
    def _notify_before_exp(self):
        today = fields.Date.today()
        expire_before = self.env.company.notify_expired_documents_before
        users = self.env.ref('raval_hr_employee_custom.notification_exp_group').user_ids
        if users:
            for rec in self.search([('exp_date', '!=', False)]).filtered(lambda x: (x.exp_date - relativedelta(days=expire_before)) <= today):
                rec.sudo().message_post(
                    author_id=self.env.ref('base.partner_root').id,
                    body=Markup('This Document for employee <a href=%s>%s</a> will expire soon.'
                    % ('/odoo/documents.document/%s' % (rec.id,), rec.partner_id.name)),
                    subject='Document Expiration Notification',
                    partner_ids=users.partner_id.ids,
                    subtype_xmlid='mail.mt_comment'
                )
