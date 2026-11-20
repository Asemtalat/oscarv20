# Copyright (C) NexGen Solutions
from odoo import models
from odoo.http import request


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    def session_info(self):
        info = super().session_info()
        if request and request.session.uid:
            user = self.env.user
            am = self.env['res.users'].get_access_restrictions()
            is_access_admin = user.has_group('access_management_ai.group_access_manager')
            switch_from_uid = request.session.get('am_switch_from_uid')
            am['is_access_admin'] = is_access_admin
            am['can_switch_user'] = bool(is_access_admin or switch_from_uid)
            if switch_from_uid:
                am['switch_from'] = {
                    'id': switch_from_uid,
                    'name': request.session.get('am_switch_from_name') or '',
                    'login': request.session.get('am_switch_from_login') or '',
                }
            info['access_management_ai'] = am
            if am.get('disable_dev_mode') and not user._is_superuser():
                # force developer/debug mode off for this user
                request.session.debug = ''
                info.get('bundle_params', {}).pop('debug', None)
            if am.get('global', {}).get('hide_spreadsheet'):
                info['can_insert_in_spreadsheet'] = False
        return info
