# Copyright (C) NexGen Solutions
from odoo import api, fields, models


class AccessLoginLog(models.Model):
    _name = 'access.login.log'
    _description = 'Access Login/Logout Log'
    _order = 'login_date desc, id desc'
    _rec_name = 'user_id'

    user_id = fields.Many2one('res.users', string='User', index=True, ondelete='cascade', domain=[('share', '=', False)])
    login = fields.Char(string='Login')
    event = fields.Selection(
        [('login', 'Login'), ('logout', 'Logout'), ('failed', 'Failed Login')],
        string='Event', required=True, index=True)
    login_date = fields.Datetime(string='Date', default=fields.Datetime.now, index=True)
    ip = fields.Char(string='IP Address')
    browser = fields.Char(string='Browser')
    platform = fields.Char(string='Platform')
    country = fields.Char(string='Country')
    city = fields.Char(string='City')
    session_id = fields.Char(string='Session')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)

    @api.model
    def _track(self, event, login=None, user=None, request=None):
        """ Write an audit entry. Safe to call from auth flows (sudo, no raise). """
        try:
            vals = {'event': event, 'login': login}
            if user:
                vals['user_id'] = user.id
                vals['login'] = login or user.login
                vals.setdefault('company_id', user.company_id.id)
            if request is not None:
                try:
                    vals['ip'] = request.httprequest.environ.get('REMOTE_ADDR')
                    vals['session_id'] = (request.session.sid or '')[:32]
                    ua = request.httprequest.user_agent
                    vals['browser'] = getattr(ua, 'browser', None)
                    vals['platform'] = getattr(ua, 'platform', None)
                except Exception:  # noqa: BLE001
                    pass
            self.sudo().create(vals)
        except Exception:  # noqa: BLE001 - auditing must never break authentication
            pass
