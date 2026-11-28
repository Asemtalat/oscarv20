from odoo import api, fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    notify_expired_documents_before = fields.Integer()


class ResConfigSetting(models.TransientModel):
    _inherit = 'res.config.settings'

    notify_expired_documents_before = fields.Integer(related='company_id.notify_expired_documents_before', readonly=False)
