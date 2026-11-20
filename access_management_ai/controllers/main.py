# Copyright (C) NexGen Solutions
from werkzeug.exceptions import Forbidden

from odoo import http, fields
from odoo.http import request
from odoo.addons.web.controllers.session import Session


class AccessManagementController(http.Controller):

    @http.route('/access_management/login_as/<int:uid>', type='jsonrpc', auth='user', methods=['POST'])
    def login_as(self, uid, **kw):
        """ Access Administrator only: switch the current session to another user. """
        admin = request.env.user
        if not admin.has_group('access_management_ai.group_access_manager'):
            raise Forbidden()
        target = request.env['res.users'].sudo().browse(uid).exists()
        if not target or target._is_superuser() or target.id == admin.id:
            raise Forbidden()
        if not target.active or target.share:
            raise Forbidden()

        # Remember the original administrator so they can switch back later.
        if not request.session.get('am_switch_from_uid'):
            request.session['am_switch_from_uid'] = admin.id
            request.session['am_switch_from_name'] = admin.name
            request.session['am_switch_from_login'] = admin.login

        request.env['access.login.log'].sudo()._track('login', user=target, request=request)
        request.session.uid = target.id
        request.session.login = target.login
        request.session.session_token = target._compute_session_token(request.session.sid)
        request.session.context = dict(target.with_user(target).context_get())
        request.session.should_rotate = True
        request.update_env(user=target.id, context=request.session.context)
        return {'redirect': '/odoo'}

    @http.route('/access_management/switch_back', type='jsonrpc', auth='user', methods=['POST'])
    def switch_back(self, **kw):
        """ Restore the Access Administrator session after Switch User. """
        from_uid = request.session.get('am_switch_from_uid')
        if not from_uid:
            return {'redirect': '/odoo'}
        original = request.env['res.users'].sudo().browse(from_uid).exists()
        request.session.pop('am_switch_from_uid', None)
        request.session.pop('am_switch_from_name', None)
        request.session.pop('am_switch_from_login', None)
        if not original or not original.active or not original.has_group('access_management_ai.group_access_manager'):
            raise Forbidden()

        request.env['access.login.log'].sudo()._track('login', user=original, request=request)
        request.session.uid = original.id
        request.session.login = original.login
        request.session.session_token = original._compute_session_token(request.session.sid)
        request.session.context = dict(original.with_user(original).context_get())
        request.session.should_rotate = True
        request.update_env(user=original.id, context=request.session.context)
        return {'redirect': '/odoo'}
    @http.route('/api/v1/access_management/requests', type='jsonrpc', auth='user', methods=['POST'])
    def api_create_access_request(self, **kwargs):
        """ Secure JSON-RPC Endpoint for submitting access requests. """
        # 1. Authenticate users: handled natively by `auth='user'` which checks the active session/token.

        # 2. Validate permissions: User must have access to create requests.
        if not request.env['access.request'].browse().has_access('create'):
            raise Forbidden("You do not have permission to submit access requests.")

        # 3. Sanitise inputs: ensure required fields are present and safe.
        role_id = kwargs.get('role_id')
        request_reason = kwargs.get('request_reason')

        if not role_id or not isinstance(role_id, int):
            return {'error': 'Invalid or missing role_id. Must be an integer.'}
        if not request_reason or not isinstance(request_reason, str) or len(request_reason.strip()) == 0:
            return {'error': 'Invalid or missing request_reason.'}

        from datetime import timedelta
        # 4. Rate Limiting Check (Simple example checking recent requests)
        recent_requests = request.env['access.request'].search_count([
            ('create_uid', '=', request.env.uid),
            ('create_date', '>=', fields.Datetime.now() - timedelta(minutes=5))
        ])
        if recent_requests >= 5:
            return {'error': 'Rate limit exceeded. Too many requests in the last 5 minutes.'}

        # Create record safely
        new_request = request.env['access.request'].create({
            'role_id': role_id,
            'request_reason': request_reason,
        })
        new_request.action_submit()

        # 5. Avoid exposing confidential fields in response.
        return {
            'success': True,
            'request_id': new_request.id,
            'state': new_request.state,
            'role_id': new_request.role_id.id,
            'role_name': new_request.role_id.name,
            # We strictly do not return admin IDs or other confidential metadata here.
        }

from odoo.addons.web.controllers.action import Action
from odoo.exceptions import AccessError
from odoo import _

class AccessManagementAction(Action):

    @http.route('/web/action/load', type='jsonrpc', auth='user', readonly=True)
    def load(self, action_id, context=None):
        try:
            act_id = int(action_id)
        except ValueError:
            act_id = None
            
        if act_id:
            rules = request.env['access.management']._rules_for_user(request.env.uid)
            if rules:
                hidden_ids = request.env['access.management']._hidden_action_ids_for_user(
                    request.env.uid,
                )
                if act_id in hidden_ids:
                    raise AccessError(_("You are not allowed to access this action."))

        return super().load(action_id, context)



class Session(Session):

    @http.route()
    def logout(self, redirect='/odoo'):
        if request.session.uid:
            user = request.env['res.users'].sudo().browse(request.session.uid)
            request.env['access.login.log'].sudo()._track('logout', user=user, request=request)
        return super().logout(redirect=redirect)
