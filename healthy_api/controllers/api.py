import json
import logging
import base64
from datetime import datetime, time
from odoo import http, _, fields
from odoo.exceptions import UserError
from odoo.http import request

_logger = logging.getLogger(__name__)


class APIController(http.Controller):
    """Main controller exposing REST endpoints under the ``/api`` prefix."""

    ROLE_GROUP_MAP = {
        'delegate': 'healthy_api.group_api_delegate',
        'supervisor': 'healthy_api.group_api_supervisor',
        'warehouse': 'healthy_api.group_api_warehouse',
        'admin': 'healthy_api.group_api_admin',
    }
    ROLE_LABEL_MAP = {
        'admin': 'Admin',
        'supervisor': 'Area Manager',
        'warehouse': 'Inventory Manager',
        'delegate': 'Delivery',
    }

    def _authenticate(self):
        """
        Authenticate the request based on a raw token passed in the
        ``Authorization`` header or a ``token`` query parameter.

        The ``Authorization`` header must contain only the token value,
        without any ``Bearer`` prefix. As a fallback, the token can also
        be supplied in the ``token`` header or as a ``token`` query
        parameter. If a matching user is found the request environment is
        updated to run as that user.

        :return: the authenticated ``res.users`` record or ``False`` when
                 authentication fails
        """
        token = None
        # Check Authorization header (raw token only)
        auth_header = request.httprequest.headers.get('Authorization')
        if auth_header:
            token = auth_header.strip()
        # Allow explicit token header too
        if not token:
            token = request.httprequest.headers.get('token')
        # Fallback to token passed as a query parameter
        if not token:
            token = request.params.get('token')
        if not token:
            return False
        Users = request.env['res.users'].sudo()
        user = False
        # 1. Match per‑day token (valid only for today)
        today = fields.Date.context_today(request.env.user)
        if token:
            user = Users.search([
                ('daily_api_token', '=', token),
                ('daily_token_date', '=', today),
            ], limit=1)
        if not user:
            return False
        if not user.has_api_access():
            return False
        # Update request env to operate as the authenticated user
        request.update_env(user=user)
        return user

    @staticmethod
    def _record_exists(record):
        return bool(record and record.exists())

    @staticmethod
    def _json_response(data=None, error=None, status=200):
        """
        Construct a consistent JSON response for the API.

        :param data: payload to return under the ``data`` key
        :param error: error message to return under the ``error`` key
        :param status: HTTP status code
        :return: flask Response with JSON content and appropriate status code
        """
        body = {'data': data, 'error': error}
        return request.make_response(json.dumps(body), headers={
            'Content-Type': 'application/json'
        }, status=status)

    def _forbidden_response(self):
        return self._json_response(error='Forbidden', status=403)

    def _user_has_rule(self, user, resource, action):
        """Return True if any of the user's api_rule_ids grants resource:action."""
        for rule in user.sudo().api_rule_ids:
            if not rule.operations:
                continue
            try:
                ops = json.loads(rule.operations)
            except (ValueError, TypeError):
                continue
            if action in ops.get(resource, []):
                return True
        return False

    def _http_action(self):
        """Map current HTTP method to a CRUD action name."""
        return {
            'POST': 'create',
            'PUT': 'update',
            'PATCH': 'update',
            'DELETE': 'delete',
        }.get(request.httprequest.method, 'read')

    def _is_admin(self, user):
        return user.is_api_admin()

    def _is_supervisor(self, user):
        return user.is_api_supervisor() or user.is_api_admin()

    def _is_warehouse(self, user):
        if user.is_api_warehouse() or user.is_api_admin():
            return True
        return self._user_has_rule(user, 'inventory', 'read')

    def _can_create_sales_docs(self, user):
        if user.is_api_delegate() or user.is_api_supervisor() or user.is_api_admin():
            return True
        return self._user_has_rule(user, 'orders', self._http_action())

    def _can_manage_merchants(self, user):
        if user.is_api_delegate() or user.is_api_admin():
            return True
        return self._user_has_rule(user, 'merchants', self._http_action())

    def _can_read_merchants(self, user):
        if user.is_api_delegate() or user.is_api_supervisor() or user.is_api_admin():
            return True
        return self._user_has_rule(user, 'merchants', 'read')

    def _can_create_orders(self, user):
        if user.is_api_delegate() or user.is_api_supervisor():
            return True
        return self._user_has_rule(user, 'orders', 'create')

    def _can_read_orders(self, user):
        if user.is_api_admin() or user.is_api_supervisor() or user.is_api_warehouse():
            return True
        return self._user_has_rule(user, 'orders', 'read')

    def _can_update_orders(self, user):
        if user.is_api_delegate() or user.is_api_supervisor():
            return True
        return self._user_has_rule(user, 'orders', 'update')

    def _can_manage_products(self, user):
        if self._is_admin(user):
            return True
        return self._user_has_rule(user, 'products', self._http_action())

    def _map_order_status_in(self, value):
        if not value:
            return None
        status = str(value).strip().lower()
        return {
            'pending': 'draft',
            'accepted': 'ready',
            'rejected': 'rejected',
            'prepared': 'prepared',
            'delivered': 'delivered',
        }.get(status, status)

    def _map_order_status_out(self, internal_status):
        status = internal_status or 'draft'
        return {
            'draft': 'pending',
            'ready': 'accepted',
            'rejected': 'rejected',
            'prepared': 'prepared',
            'delivered': 'delivered',
            'handover': 'accepted',
        }.get(status, status)

    def _is_valid_order_transition(self, old_status, new_status):
        allowed = {
            'draft': {'ready', 'rejected'},
            'ready': {'prepared'},
            'rejected': {'prepared'},
            'prepared': {'delivered'},
            'delivered': set(),
            'handover': {'delivered'},
        }
        if old_status == new_status:
            return True
        return new_status in allowed.get(old_status or 'draft', set())

    def _can_manage_invoices(self, user):
        if user.is_api_delegate():
            return True
        return self._user_has_rule(user, 'invoices', self._http_action())

    def _can_access_itineraries(self, user):
        if user.is_api_delegate() or user.is_api_supervisor():
            return True
        return self._user_has_rule(user, 'deliveries', 'read')

    def _invoice_payment_method(self, invoice):
        if 'invoice_payment_ref' in invoice._fields:
            return invoice.invoice_payment_ref or ''
        if 'payment_reference' in invoice._fields:
            return invoice.payment_reference or ''
        if 'ref' in invoice._fields:
            return invoice.ref or ''
        return ''

    def _invoice_order_id(self, invoice):
        if not invoice.invoice_origin:
            return None
        order = request.env['sale.order'].sudo().search([('name', '=', invoice.invoice_origin)], limit=1)
        return order.id if order else None

    def _get_scope_user_ids(self, user):
        if self._is_admin(user):
            return request.env['res.users'].sudo().search([]).ids
        if self._is_supervisor(user):
            return (user | user.sudo().subordinate_ids).ids
        return [user.id]

    def _can_manage_user(self, auth_user, target_user):
        if self._is_admin(auth_user):
            return True
        if self._is_supervisor(auth_user):
            return target_user.id in self._get_scope_user_ids(auth_user)
        return auth_user.id == target_user.id

    def _can_assign_user(self, auth_user, target_user):
        if self._is_admin(auth_user):
            return True
        if self._is_supervisor(auth_user):
            return target_user.id in target_user.sudo().search([
                ('supervisor_id', '=', auth_user.id)
            ]).ids
        return False

    def _can_access_partner(self, auth_user, partner):
        if self._is_admin(auth_user):
            return True
        assigned_user = partner.user_id
        if not assigned_user:
            return True
        return assigned_user.id in self._get_scope_user_ids(auth_user)

    def _order_domain_for_user(self, auth_user):
        if self._is_admin(auth_user):
            return []
        if self._is_warehouse(auth_user) and not auth_user.is_api_supervisor():
            return [('warehouse_status', 'in', ['draft', 'prepared', 'ready', 'handover', 'rejected', 'delivered'])]
        return [('user_id', 'in', self._get_scope_user_ids(auth_user))]

    def _invoice_domain_for_user(self, auth_user, move_type='out_invoice'):
        domain = [('move_type', '=', move_type)]
        if self._is_admin(auth_user):
            return domain
        return domain + [('invoice_user_id', 'in', self._get_scope_user_ids(auth_user))]

    def _payment_domain_for_user(self, auth_user, target_user):
        domain = [('partner_type', '=', 'customer'), ('state', '=', 'posted')]
        if self._is_admin(auth_user):
            return domain
        return domain + [('create_uid', '=', target_user.id)]

    def _merchant_domain_for_user(self, auth_user):
        domain = [('customer_rank', '>', 0)]
        if self._is_admin(auth_user):
            return domain
        return domain + ['|', ('user_id', '=', False), ('user_id', 'in', self._get_scope_user_ids(auth_user))]

    def _get_user_by_id(self, user_id):
        return request.env['res.users'].sudo().browse(int(user_id)).exists()

    def _get_partner_by_id(self, partner_id):
        return request.env['res.partner'].sudo().browse(int(partner_id)).exists()

    def _get_order_by_id(self, order_id):
        return request.env['sale.order'].sudo().browse(int(order_id)).exists()

    def _get_invoice_by_id(self, invoice_id):
        return request.env['account.move'].sudo().browse(int(invoice_id)).exists()

    def _get_product_by_any_id(self, product_id):
        pid = int(product_id)
        product = request.env['product.product'].sudo().browse(pid).exists()
        if product:
            return product
        template = request.env['product.template'].sudo().browse(pid).exists()
        if not template:
            return request.env['product.product'].sudo().browse(False)
        variant = template.product_variant_id or template.product_variant_ids[:1]
        return variant.exists()

    def _get_signup_request_by_id(self, request_id):
        return request.env['api.signup.request'].sudo().browse(int(request_id)).exists()

    def _has_model(self, model_name):
        return model_name in request.env.registry.models

    def _role_keys_for_user(self, user):
        roles = []
        if user.is_api_admin():
            roles.append('admin')
        if user.is_api_supervisor():
            roles.append('supervisor')
        if user.is_api_warehouse():
            roles.append('warehouse')
        if user.is_api_delegate():
            roles.append('delegate')
        return roles

    def _primary_role_label(self, user):
        roles = self._role_keys_for_user(user)
        if not roles:
            return 'User'
        return self.ROLE_LABEL_MAP.get(roles[0], 'User')

    def _resolve_login_identifier(self, login_or_mobile):
        Users = request.env['res.users'].sudo()
        user = Users.search([
            '|', '|',
            ('login', '=', login_or_mobile),
            ('email', '=', login_or_mobile),
            ('partner_id.mobile', '=', login_or_mobile),
        ], limit=1)
        return user.login if user else login_or_mobile

    def _roles_from_payload(self, payload):
        value = payload.get('role')
        if value and not payload.get('roles'):
            payload = dict(payload)
            payload['roles'] = [value]
        raw_roles = payload.get('roles') or []
        if not isinstance(raw_roles, list):
            return None
        alias_map = {
            'delivery': 'delegate',
            'delegate': 'delegate',
            'area_manager': 'supervisor',
            'area manager': 'supervisor',
            'supervisor': 'supervisor',
            'inventory_manager': 'warehouse',
            'inventory manager': 'warehouse',
            'warehouse': 'warehouse',
            'admin': 'admin',
        }
        normalized = []
        for role in raw_roles:
            if not isinstance(role, str):
                return None
            mapped = alias_map.get(role.strip().lower())
            if not mapped:
                return None
            normalized.append(mapped)
        return list(dict.fromkeys(normalized))

    def _serialize_user(self, user):
        role_keys = self._role_keys_for_user(user)
        return {
            'id': user.id,
            'name': user.name,
            'login': user.login,
            'role': ', '.join(user.api_role_labels()) or 'User',
            'role_key': role_keys[0] if role_keys else None,
            'role_label': self._primary_role_label(user),
            'roles': role_keys,
            'active': user.active,
            'partner_id': user.partner_id.id,
            'email': user.email or '',
            'mobile': user.partner_id.mobile or '',
            'supervisor_id': user.supervisor_id.id if user.supervisor_id else None,
            'area_name': user.area_name or '',
            'api_rules': [{'id': r.id, 'name': r.name, 'operations': r.operations} for r in getattr(user, 'api_rule_ids', [])],
        }

    def _serialize_invoice_summary(self, inv):
        paid_amount = inv.amount_total - inv.amount_residual
        due_amount = inv.amount_residual
        payment_date = inv.invoice_date_due or inv.invoice_date
        return {
            'id': inv.id,
            'name': inv.name,
            'status': inv.state,
            'amount_total': inv.amount_total,
            'paid_amount': paid_amount,
            'due_amount': due_amount,
            'payment_status': inv.payment_state,
            'payment_date': payment_date.isoformat() if payment_date else None,
            'partner_id': inv.partner_id.id,
            'invoice_user_id': inv.invoice_user_id.id,
        }

    def _serialize_signup_request(self, signup_request):
        return {
            'id': signup_request.id,
            'name': signup_request.name,
            'email': signup_request.email,
            'mobile': signup_request.mobile,
            'state': signup_request.state,
            'created_user_id': signup_request.created_user_id.id if signup_request.created_user_id else None,
            'requested_at': signup_request.create_date.isoformat() if signup_request.create_date else None,
            'reviewed_at': signup_request.reviewed_at.isoformat() if signup_request.reviewed_at else None,
            'reviewed_by_id': signup_request.reviewed_by_id.id if signup_request.reviewed_by_id else None,
            'reject_reason': signup_request.reject_reason or '',
        }

    def _serialize_product(self, product):
        template = product.product_tmpl_id
        return {
            'id': product.id,
            'template_id': template.id,
            'name': product.display_name,
            'default_code': product.default_code or '',
            'barcode': product.barcode or '',
            'price': product.lst_price,
            'tax_ids': product.taxes_id.ids,
            'active': product.active,
            'sale_ok': product.sale_ok,
            'purchase_ok': product.purchase_ok,
            'categ_id': template.categ_id.id if template.categ_id else None,
        }

    def _product_vals_from_payload(self, payload, creating=False):
        vals = {}

        if creating and not payload.get('name'):
            return None, self._json_response(error='Missing required field: name', status=400)

        if 'name' in payload:
            vals['name'] = payload.get('name')
        if 'price' in payload:
            try:
                vals['list_price'] = float(payload.get('price'))
            except (TypeError, ValueError):
                return None, self._json_response(error='Invalid price', status=400)
        elif 'list_price' in payload:
            try:
                vals['list_price'] = float(payload.get('list_price'))
            except (TypeError, ValueError):
                return None, self._json_response(error='Invalid list_price', status=400)
        if 'active' in payload:
            vals['active'] = bool(payload.get('active'))
        if 'sale_ok' in payload:
            vals['sale_ok'] = bool(payload.get('sale_ok'))
        if 'purchase_ok' in payload:
            vals['purchase_ok'] = bool(payload.get('purchase_ok'))
        categ_id = payload.get('categ_id') if 'categ_id' in payload else payload.get('category_id')
        if categ_id is not None:
            try:
                category = request.env['product.category'].sudo().browse(int(categ_id)).exists()
            except Exception:
                return None, self._json_response(error='Invalid categ_id', status=400)
            if not category:
                return None, self._json_response(error='Category not found', status=404)
            vals['categ_id'] = category.id
        tax_ids = payload.get('tax_ids')
        if tax_ids is not None:
            if not isinstance(tax_ids, list):
                return None, self._json_response(error='tax_ids must be a list', status=400)
            taxes = request.env['account.tax'].sudo().browse(tax_ids).exists()
            if len(taxes) != len(tax_ids):
                return None, self._json_response(error='One or more tax_ids are invalid', status=400)
            vals['taxes_id'] = [(6, 0, taxes.ids)]
        return vals, None

    def _set_user_roles(self, user, roles):
        group_commands = []
        all_group_ids = [
            request.env.ref(xmlid).id
            for xmlid in self.ROLE_GROUP_MAP.values()
        ]
        group_commands.append((3, request.env.ref('base.group_portal').id))
        for group_id in all_group_ids:
            group_commands.append((3, group_id))
        for role in roles:
            xmlid = self.ROLE_GROUP_MAP.get(role)
            if xmlid:
                group_commands.append((4, request.env.ref(xmlid).id))
        user.sudo().write({'groups_id': group_commands})

    def _parse_json_payload(self):
        try:
            payload = json.loads(request.httprequest.data or '{}')
        except ValueError:
            return None
        if isinstance(payload, dict) and isinstance(payload.get('params'), dict):
            payload = payload['params']
        return payload if isinstance(payload, dict) else None

    def _get_requested_user(self, auth_user, allow_self=True):
        user_id = request.params.get('user_id')
        if user_id:
            try:
                target_user = self._get_user_by_id(user_id)
            except Exception:
                return None, self._json_response(error='Invalid user_id', status=400)
        else:
            target_user = auth_user if allow_self else None
        if not self._record_exists(target_user):
            return None, self._json_response(error='User not found', status=404)
        if not self._can_manage_user(auth_user, target_user):
            return None, self._forbidden_response()
        return target_user, None

    def _create_user_from_signup_request(self, signup_request, auth_user):
        try:
            created_user = signup_request.with_user(auth_user).approve_and_create_user()
        except UserError as exc:
            message = str(exc) or 'Unable to approve signup request'
            status = 409 if 'already in use' in message.lower() else 400
            return None, self._json_response(error=message, status=status)
        return created_user, None

    def _issue_login_token(self, user):
        token = user.generate_daily_api_token()
        return self._json_response(data={
            'token': token,
            'uid': user.id,
            'roles': user.api_role_labels(),
            'user': {
                'id': user.id,
                'name': user.name,
                'role': self._primary_role_label(user),
            },
        })

    # ---------------------------------------------------------------------
    # User endpoint
    # ---------------------------------------------------------------------
    @http.route(['/api/users'], type='http', auth='public', methods=['GET'], csrf=False)
    def get_users(self, **kwargs):

        user = self._authenticate()
        if not user:
            return self._json_response(error='Unauthorized', status=401)
        if self._is_admin(user):
            domain = [('share', '=', False), ('active', '=', True)]
        elif self._is_supervisor(user):
            domain = [('id', 'in', self._get_scope_user_ids(user)), ('share', '=', False), ('active', '=', True)]
        else:
            domain = [('id', '=', user.id)]
        users = request.env['res.users'].sudo().search(domain)
        result = []
        for u in users:
            result.append(self._serialize_user(u))
        return self._json_response(data=result)

    # ---------------------------------------------------------------------
    # Daily Token
    # ---------------------------------------------------------------------
    @http.route(['/api/daily_token'], type='http', auth='public', methods=['GET'], csrf=False)
    def daily_token(self, **kwargs):
        return self._json_response(
            error='Deprecated endpoint. Use POST /auth/login to get the daily token.',
            status=410,
        )

    # ---------------------------------------------------------------------
    # Login to generate daily token
    # ---------------------------------------------------------------------
    @http.route(['/auth/signup'], type='http', auth='public', methods=['POST'], csrf=False)
    def auth_signup(self, **kwargs):
        payload = self._parse_json_payload()
        if not payload:
            return self._json_response(error='Invalid JSON payload', status=400)
        name = payload.get('name')
        email = payload.get('email')
        mobile = payload.get('mobile')
        password = payload.get('password')
        if not all([name, email, mobile, password]):
            return self._json_response(
                error='Missing required fields: name, email, mobile, password',
                status=400,
            )
        Users = request.env['res.users'].sudo()
        if Users.search_count(['|', ('login', '=', email), ('partner_id.mobile', '=', mobile)]):
            return self._json_response(error='User already exists', status=409)
        SignupRequest = request.env['api.signup.request'].sudo()
        existing_pending = SignupRequest.search([
            ('state', '=', 'pending'),
            '|',
            ('email', '=', email),
            ('mobile', '=', mobile),
        ], limit=1)
        if existing_pending:
            return self._json_response(error='Signup request already pending', status=409)
        signup_request = SignupRequest.create({
            'name': name,
            'email': email,
            'mobile': mobile,
            'password': password,
            'state': 'pending',
        })
        return self._json_response(data={
            'message': 'Signup successful. Await admin approval.',
            'user_id': signup_request.id,
            'signup_request_id': signup_request.id,
        }, status=201)

    @http.route(['/api/login', '/auth/login'], type='http', auth='public', methods=['POST'], csrf=False)
    def api_login(self, **kwargs):
        """
        Authenticate a user using their login credentials and return a
        per‑day API token. Clients should call this endpoint once per day
        to obtain a token that will remain valid until midnight (server
        timezone). Subsequent calls on the same day will return the same
        token.

        Request payload should be JSON with ``login`` and ``password``
        fields only.

        **Example request:**
        ``POST /api/login`` with body ``{"login": "user@example.com", "password": "secret"}``

        **Example response:**
        ``{"token": "abc123...", "uid": 5}``
        """
        payload = self._parse_json_payload()
        if not payload:
            return self._json_response(error='Invalid JSON payload', status=400)
        login = payload.get('login') or payload.get('email_or_mobile')
        password = payload.get('password')
        if not login or not password:
            return self._json_response(error='Missing login or password', status=400)
        pending_signup = request.env['api.signup.request'].sudo().search([
            ('state', '=', 'pending'),
            '|',
            ('email', '=', login),
            ('mobile', '=', login),
        ], limit=1)
        if pending_signup:
            return self._json_response(data={
                'status': 'pending_admin_approval',
                'signup_request_id': pending_signup.id,
            }, error='Account pending admin approval', status=403)
        login = self._resolve_login_identifier(login)
        credential = {
            'type': 'password',
            'login': login,
            'password': password,
        }
        try:
            auth_info = request.env['res.users'].sudo().authenticate(
                request.env.cr.dbname,
                credential,
                {'interactive': False},
            )
            uid = auth_info.get('uid')
        except Exception as e:
            _logger.warning('Authentication failed for %s: %s', login, e)
            return self._json_response(error='Invalid credentials', status=401)
        if not uid:
            return self._json_response(error='Invalid credentials', status=401)
        user = request.env['res.users'].sudo().browse(uid).exists()
        if not user:
            return self._json_response(error='Invalid credentials', status=401)
        if not user.has_api_access():
            return self._json_response(error='User does not have API access', status=403)
        if not user.active or user.api_user_state == 'pending_approval':
            return self._json_response(data={
                'status': 'pending_admin_approval',
                'user_id': user.id,
            }, error='Account pending admin approval', status=403)
        if user.api_user_state == 'archived':
            return self._json_response(error='Account is inactive', status=403)
        return self._issue_login_token(user)

    @http.route(['/users', '/users/<int:user_id>'], type='http', auth='public',
                methods=['GET', 'POST', 'PUT', 'DELETE'], csrf=False)
    def users_crud(self, user_id=None, **kwargs):
        auth_user = self._authenticate()
        if not auth_user:
            return self._json_response(error='Unauthorized', status=401)
        if not self._is_admin(auth_user):
            return self._forbidden_response()

        Users = request.env['res.users'].sudo()
        method = request.httprequest.method

        if method == 'GET':
            if user_id:
                user = Users.browse(user_id).exists()
                if not user:
                    return self._json_response(error='User not found', status=404)
                return self._json_response(data=self._serialize_user(user))
            users = Users.search([('share', '=', False)])
            return self._json_response(data=[self._serialize_user(u) for u in users])

        payload = self._parse_json_payload()
        if not payload:
            return self._json_response(error='Invalid JSON payload', status=400)

        if method == 'POST':
            for required_field in ('name', 'email', 'password'):
                if not payload.get(required_field):
                    return self._json_response(error='Missing required field: %s' % required_field, status=400)
            roles = self._roles_from_payload(payload)
            if roles is None:
                return self._json_response(error='Invalid roles list', status=400)
            if Users.search_count([('login', '=', payload.get('email'))]):
                return self._json_response(error='User already exists', status=409)
            user = Users.create({
                'name': payload.get('name'),
                'login': payload.get('email'),
                'email': payload.get('email'),
                'password': payload.get('password'),
                'active': payload.get('active', True),
                'area_name': payload.get('area_name') or False,
            })
            if payload.get('mobile') and user.partner_id:
                user.partner_id.sudo().write({'mobile': payload.get('mobile')})
            if roles:
                self._set_user_roles(user, roles)
            return self._json_response(data=self._serialize_user(user), status=201)

        if not user_id:
            return self._json_response(error='Missing user_id in route', status=400)
        user = Users.browse(user_id).exists()
        if not user:
            return self._json_response(error='User not found', status=404)

        if method == 'PUT':
            vals = {}
            if 'name' in payload:
                vals['name'] = payload.get('name')
            if 'email' in payload:
                vals['email'] = payload.get('email')
                vals['login'] = payload.get('email')
            if 'password' in payload and payload.get('password'):
                vals['password'] = payload.get('password')
            if 'active' in payload:
                vals['active'] = bool(payload.get('active'))
            if 'area_name' in payload:
                vals['area_name'] = payload.get('area_name') or False
            if vals:
                user.write(vals)
            if 'mobile' in payload and user.partner_id:
                user.partner_id.sudo().write({'mobile': payload.get('mobile') or False})
            roles = self._roles_from_payload(payload)
            if roles is None:
                return self._json_response(error='Invalid roles list', status=400)
            if roles:
                self._set_user_roles(user, roles)
            return self._json_response(data=self._serialize_user(user))

        try:
            user.sudo().unlink()
            return self._json_response(data={'message': 'User deleted'})
        except Exception:
            user.write({'active': False, 'api_user_state': 'archived'})
            return self._json_response(data={'message': 'User archived (linked records prevent hard delete)'})

    @http.route(['/users/<int:user_id>/approve'], type='http', auth='public', methods=['PUT'], csrf=False)
    def approve_user(self, user_id, **kwargs):
        auth_user = self._authenticate()
        if not auth_user:
            return self._json_response(error='Unauthorized', status=401)
        if not self._is_admin(auth_user):
            return self._forbidden_response()
        user = self._get_user_by_id(user_id)
        if user:
            user.sudo().write({'active': True, 'api_user_state': 'approved'})
            return self._json_response(data=self._serialize_user(user))

        signup_request = self._get_signup_request_by_id(user_id)
        if not signup_request:
            return self._json_response(error='User or signup request not found', status=404)
        if signup_request.state != 'pending':
            return self._json_response(error='Signup request is not pending', status=400)
        created_user, error_response = self._create_user_from_signup_request(signup_request, auth_user)
        if error_response:
            return error_response
        return self._json_response(data=self._serialize_user(created_user))

    @http.route(['/users/<int:user_id>/role'], type='http', auth='public', methods=['PUT'], csrf=False)
    def assign_user_role(self, user_id, **kwargs):
        auth_user = self._authenticate()
        if not auth_user:
            return self._json_response(error='Unauthorized', status=401)
        if not self._is_admin(auth_user):
            return self._forbidden_response()
        user = self._get_user_by_id(user_id)
        if not user:
            return self._json_response(error='User not found', status=404)
        payload = self._parse_json_payload()
        if not payload:
            return self._json_response(error='Invalid JSON payload', status=400)
        roles = self._roles_from_payload(payload)
        if roles is None:
            return self._json_response(error='Invalid roles list', status=400)
        self._set_user_roles(user, roles)
        return self._json_response(data=self._serialize_user(user))

    # ---------------------------------------------------------------------
    # Merchants (Customers)
    # ---------------------------------------------------------------------
    @http.route(['/api/merchants', '/merchants'], type='http', auth='public', methods=['GET', 'POST'], csrf=False)
    def merchants(self, **kwargs):
        """
        GET: Return a list of customer partners with basic contact data.
        POST: Create a new merchant (customer) in Odoo using the JSON
        payload provided in the request body. Only minimal fields are
        required: name and optionally phone, email, vat and address.
        """
        auth_user = self._authenticate()
        if not auth_user:
            return self._json_response(error='Unauthorized', status=401)
        if request.httprequest.method == 'GET':
            if not self._can_read_merchants(auth_user):
                return self._forbidden_response()
            customers = request.env['res.partner'].sudo().search(self._merchant_domain_for_user(auth_user))
            data = []
            for partner in customers:
                data.append({
                    'id': partner.id,
                    'merchant_code': partner.ref or '',
                    'name': partner.name,
                    'mobile': partner.mobile or partner.phone or '',
                    'phone': partner.phone or '',
                    'address': partner.contact_address or '',
                    'commercial_registration': partner.company_registry or '',
                    'tax_card': partner.vat or '',
                    'vat': partner.vat or '',
                    'gps_latitude': partner.partner_latitude or 0.0,
                    'gps_longitude': partner.partner_longitude or 0.0,
                    'assigned_user_id': partner.user_id.id if partner.user_id else None,
                })
            return self._json_response(data=data)
        else:
            if not self._can_manage_merchants(auth_user):
                return self._forbidden_response()
            # POST: create a new customer
            payload = self._parse_json_payload()
            if not payload:
                return self._json_response(error='Invalid JSON payload', status=400)
            name = payload.get('name')
            if not name:
                return self._json_response(error='Missing required field: name', status=400)
            assigned_user = auth_user
            assigned_user_id = payload.get('assigned_user_id') or payload.get('user_id')
            if assigned_user_id:
                try:
                    assigned_user = self._get_user_by_id(assigned_user_id)
                except Exception:
                    return self._json_response(error='Invalid assigned_user_id', status=400)
                if not self._record_exists(assigned_user):
                    return self._json_response(error='Assigned user not found', status=404)
                if not self._can_assign_user(auth_user, assigned_user):
                    return self._forbidden_response()
            vals = {
                'name': name,
                'ref': payload.get('merchant_code') or False,
                'phone': payload.get('mobile') or payload.get('phone'),
                'mobile': payload.get('mobile') or payload.get('phone'),
                'email': payload.get('email'),
                'vat': payload.get('tax_card') or payload.get('vat'),
                'company_registry': payload.get('commercial_registration') or False,
                'street': payload.get('address') or payload.get('street'),
                'city': payload.get('city'),
                'zip': payload.get('zip'),
                'customer_rank': 1,
                'user_id': assigned_user.id,
            }
            partner = request.env['res.partner'].sudo().create(vals)
            return self._json_response(data={'id': partner.id})

    @http.route(['/merchants/<int:merchant_id>', '/api/merchants/<int:merchant_id>'],
                type='http', auth='public', methods=['GET', 'PUT', 'DELETE'], csrf=False)
    def merchant_detail(self, merchant_id, **kwargs):
        auth_user = self._authenticate()
        if not auth_user:
            return self._json_response(error='Unauthorized', status=401)
        partner = self._get_partner_by_id(merchant_id)
        if not self._record_exists(partner) or partner.customer_rank <= 0:
            return self._json_response(error='Merchant not found', status=404)
        method = request.httprequest.method

        if method == 'GET':
            if not self._can_read_merchants(auth_user):
                return self._forbidden_response()
            if not self._can_access_partner(auth_user, partner):
                return self._forbidden_response()
            return self._json_response(data={
                'id': partner.id,
                'merchant_code': partner.ref or '',
                'name': partner.name,
                'mobile': partner.mobile or partner.phone or '',
                'address': partner.contact_address or '',
                'commercial_registration': partner.company_registry or '',
                'tax_card': partner.vat or '',
                'assigned_user_id': partner.user_id.id if partner.user_id else None,
            })

        if method == 'DELETE':
            if not self._is_admin(auth_user):
                return self._forbidden_response()
            partner.sudo().unlink()
            return self._json_response(data={'message': 'Merchant deleted'})

        if not self._can_manage_merchants(auth_user):
            return self._forbidden_response()
        if not self._can_access_partner(auth_user, partner):
            return self._forbidden_response()
        payload = self._parse_json_payload()
        if not payload:
            return self._json_response(error='Invalid JSON payload', status=400)
        vals = {}
        if 'name' in payload:
            vals['name'] = payload.get('name')
        if 'mobile' in payload:
            vals['mobile'] = payload.get('mobile')
            vals['phone'] = payload.get('mobile')
        if 'address' in payload:
            vals['street'] = payload.get('address')
        if 'tax_card' in payload:
            vals['vat'] = payload.get('tax_card')
        if 'commercial_registration' in payload:
            vals['company_registry'] = payload.get('commercial_registration')
        assigned_user_id = payload.get('assigned_user_id') or payload.get('user_id')
        if assigned_user_id:
            try:
                assigned_user = self._get_user_by_id(int(assigned_user_id))
            except Exception:
                return self._json_response(error='Invalid assigned_user_id', status=400)
            if not self._record_exists(assigned_user):
                return self._json_response(error='Assigned user not found', status=404)
            if not self._can_assign_user(auth_user, assigned_user):
                return self._forbidden_response()
            vals['user_id'] = assigned_user.id
        if vals:
            partner.sudo().write(vals)
        return self._json_response(data={'id': partner.id})

    # ---------------------------------------------------------------------
    # Products
    # ---------------------------------------------------------------------
    @http.route(['/api/products'], type='http', auth='public', methods=['GET', 'POST'], csrf=False)
    def products(self, **kwargs):
        """Return products or create a new product."""
        auth_user = self._authenticate()
        if not auth_user:
            return self._json_response(error='Unauthorized', status=401)
        if request.httprequest.method == 'GET':
            products = request.env['product.product'].sudo().search([
                ('sale_ok', '=', True),
                ('active', '=', True),
            ])
            return self._json_response(data=[self._serialize_product(prod) for prod in products])

        if not self._can_manage_products(auth_user):
            return self._forbidden_response()
        payload = self._parse_json_payload()
        if not payload:
            return self._json_response(error='Invalid JSON payload', status=400)
        vals, error_response = self._product_vals_from_payload(payload, creating=True)
        if error_response:
            return error_response
        template = request.env['product.template'].sudo().create(vals)
        product = template.product_variant_id or template.product_variant_ids[:1]
        variant_vals = {}
        if 'default_code' in payload:
            variant_vals['default_code'] = payload.get('default_code') or False
        if 'barcode' in payload:
            variant_vals['barcode'] = payload.get('barcode') or False
        if variant_vals and product:
            product.sudo().write(variant_vals)
        return self._json_response(data=self._serialize_product(product), status=201)

    @http.route(['/api/products/<int:product_id>'], type='http', auth='public',
                methods=['GET', 'PUT', 'DELETE'], csrf=False)
    def product_detail(self, product_id, **kwargs):
        auth_user = self._authenticate()
        if not auth_user:
            return self._json_response(error='Unauthorized', status=401)
        product = self._get_product_by_any_id(product_id)
        if not self._record_exists(product):
            return self._json_response(error='Product not found', status=404)

        method = request.httprequest.method
        if method == 'GET':
            return self._json_response(data=self._serialize_product(product))

        if not self._can_manage_products(auth_user):
            return self._forbidden_response()

        if method == 'DELETE':
            try:
                product.sudo().unlink()
                return self._json_response(data={'message': 'Product deleted'})
            except Exception:
                product.product_tmpl_id.sudo().write({'active': False})
                return self._json_response(data={'message': 'Product archived (linked records prevent hard delete)'})

        payload = self._parse_json_payload()
        if not payload:
            return self._json_response(error='Invalid JSON payload', status=400)
        vals, error_response = self._product_vals_from_payload(payload, creating=False)
        if error_response:
            return error_response
        variant_vals = {}
        if 'default_code' in payload:
            variant_vals['default_code'] = payload.get('default_code') or False
        if 'barcode' in payload:
            variant_vals['barcode'] = payload.get('barcode') or False
        if vals:
            product.product_tmpl_id.sudo().write(vals)
        if variant_vals:
            product.sudo().write(variant_vals)
        return self._json_response(data=self._serialize_product(product))

    # ---------------------------------------------------------------------
    # Stock / Inventory
    # ---------------------------------------------------------------------
    @http.route(['/api/stock'], type='http', auth='public', methods=['GET'], csrf=False)
    def stock(self, **kwargs):
        """
        Return available stock quantities grouped by product and location. The
        endpoint accepts optional query parameters ``product_id`` and
        ``location_id`` to filter the results. If not provided all
        combinations are returned.
        """
        auth_user = self._authenticate()
        if not auth_user:
            return self._json_response(error='Unauthorized', status=401)
        if not self._is_warehouse(auth_user):
            return self._forbidden_response()
        domain = []
        product_id = request.params.get('product_id')
        location_id = request.params.get('location_id')
        if product_id:
            try:
                product_id = int(product_id)
                domain.append(('product_id', '=', product_id))
            except Exception:
                return self._json_response(error='Invalid product_id', status=400)
        if location_id:
            try:
                location_id = int(location_id)
                domain.append(('location_id', '=', location_id))
            except Exception:
                return self._json_response(error='Invalid location_id', status=400)
        quants = request.env['stock.quant'].sudo().search(domain)
        data = []
        for q in quants:
            data.append({
                'product_id': q.product_id.id,
                'location_id': q.location_id.id,
                'quantity': q.quantity,
            })
        return self._json_response(data=data)

    # ---------------------------------------------------------------------
    # Delivery Person Stock
    # ---------------------------------------------------------------------
    @http.route(['/api/delivery_stock'], type='http', auth='public', methods=['GET'], csrf=False)
    def delivery_stock(self, **kwargs):
        """
        Return the stock assigned to a specific delivery user. Stock is
        determined by looking at quants whose owner matches the user's
        partner record. If no ``user_id`` is passed via query parameter the
        authenticated user is used.
        """
        auth_user = self._authenticate()
        if not auth_user:
            return self._json_response(error='Unauthorized', status=401)
        user_id = request.params.get('user_id')
        if user_id:
            try:
                user_id = int(user_id)
            except Exception:
                return self._json_response(error='Invalid user_id', status=400)
            user = self._get_user_by_id(user_id)
        else:
            user = auth_user
        if not self._record_exists(user):
            return self._json_response(error='User not found', status=404)
        if not self._can_manage_user(auth_user, user):
            return self._forbidden_response()
        # Use owner_id on stock.quant to represent stock owned/assigned to the user
        partner_id = user.partner_id.id
        quants = request.env['stock.quant'].sudo().search([
            ('owner_id', '=', partner_id)
        ])
        data = []
        for q in quants:
            data.append({
                'order_id': None,
                'delivery_id': user.id,
                'product_id': q.product_id.id,
                'product_name': q.product_id.display_name,
                'quantity': q.quantity,
                'quantity_available': q.quantity,
            })
        return self._json_response(data=data)

    @http.route(['/warehouses', '/api/warehouses'], type='http', auth='public', methods=['GET'], csrf=False)
    def warehouses(self, **kwargs):
        auth_user = self._authenticate()
        if not auth_user:
            return self._json_response(error='Unauthorized', status=401)
        if not auth_user.is_api_delegate():
            return self._forbidden_response()

        today = fields.Date.today()
        start = datetime.combine(today, time.min)
        end = datetime.combine(today, time.max)

        orders = request.env['sale.order'].sudo().search([
            ('user_id', '=', auth_user.id),
            ('date_order', '>=', start),
            ('date_order', '<=', end),
        ], order='date_order asc, id asc')

        quant_map = {}
        partner_id = auth_user.partner_id.id
        quants = request.env['stock.quant'].sudo().search([('owner_id', '=', partner_id)])
        for quant in quants:
            quant_map[quant.product_id.id] = quant_map.get(quant.product_id.id, 0.0) + quant.quantity

        data = []
        for order in orders:
            products = []
            total_available = 0.0
            for line in order.order_line:
                qty_available = quant_map.get(line.product_id.id, 0.0)
                total_available += qty_available
                products.append({
                    'product_id': line.product_id.id,
                    'product_name': line.product_id.display_name,
                    'ordered_quantity': line.product_uom_qty,
                    'quantity_available': qty_available,
                })
            data.append({
                'order_id': order.id,
                'delivery_id': auth_user.id,
                'products': products,
                'quantity_available': total_available,
            })
        return self._json_response(data=data)

    @http.route(['/api/delivery_stock/adjust'], type='http', auth='public', methods=['POST'], csrf=False)
    def delivery_stock_adjust(self, **kwargs):
        """
        Adjust the stock of a delivery person. The JSON payload must
        include ``user_id``, ``product_id`` and ``quantity`` fields. A
        positive quantity increases the stock whereas a negative quantity
        reduces it. The adjustment is applied directly to the quant owned
        by the user. If no quant exists it will be created.
        """
        auth_user = self._authenticate()
        if not auth_user:
            return self._json_response(error='Unauthorized', status=401)
        if not self._is_admin(auth_user):
            return self._forbidden_response()
        payload = self._parse_json_payload()
        if not payload:
            return self._json_response(error='Invalid JSON payload', status=400)
        user_id = payload.get('user_id')
        product_id = payload.get('product_id')
        qty = payload.get('quantity')
        if not all([user_id, product_id, qty]):
            return self._json_response(error='Missing user_id, product_id or quantity', status=400)
        try:
            user = self._get_user_by_id(int(user_id))
            product = request.env['product.product'].sudo().browse(int(product_id)).exists()
            qty = float(qty)
        except Exception:
            return self._json_response(error='Invalid parameter types', status=400)
        if not self._record_exists(user) or not self._record_exists(product):
            return self._json_response(error='User or product not found', status=404)
        partner_id = user.partner_id.id
        quant = request.env['stock.quant'].sudo().search([
            ('owner_id', '=', partner_id),
            ('product_id', '=', product.id)
        ], limit=1)
        if quant:
            quant.quantity += qty
        else:
            # Create a new quant assigned to user in the first internal location
            location = request.env['stock.location'].sudo().search([('usage', '=', 'internal')], limit=1)
            request.env['stock.quant'].sudo().create({
                'product_id': product.id,
                'location_id': location.id,
                'owner_id': partner_id,
                'quantity': qty,
            })
        return self._json_response(data={'message': 'Stock adjusted successfully'})

    # ---------------------------------------------------------------------
    # Sales Orders
    # ---------------------------------------------------------------------
    @http.route(['/api/orders', '/api/orders/<int:order_id>', '/orders', '/orders/<int:order_id>'],
                type='http', auth='public', methods=['GET', 'POST'], csrf=False)
    def orders(self, order_id=None, **kwargs):
        """
        GET /api/orders                -> list sales orders for the authenticated user
        GET /api/orders/<order_id>     -> retrieve details of a specific order
        POST /api/orders               -> create a new sales order from the JSON payload
        """
        auth_user = self._authenticate()
        if not auth_user:
            return self._json_response(error='Unauthorized', status=401)
        if request.httprequest.method == 'GET':
            if not self._can_read_orders(auth_user):
                return self._forbidden_response()
            if order_id:
                order = self._get_order_by_id(order_id)
                if not self._record_exists(order):
                    return self._json_response(error='Order not found', status=404)
                if not order.sudo().search_count([('id', '=', order.id)] + self._order_domain_for_user(auth_user)):
                    return self._forbidden_response()
                lines = []
                for line in order.order_line:
                    lines.append({
                        'product_id': line.product_id.id,
                        'product_name': line.product_id.display_name,
                        'quantity': line.product_uom_qty,
                        'price_unit': line.price_unit,
                        'subtotal': line.price_subtotal,
                    })
                result = {
                    'id': order.id,
                    'name': order.name,
                    'status': self._map_order_status_out(order.warehouse_status),
                    'warehouse_status': order.warehouse_status,
                    'date_order': order.date_order.isoformat() if order.date_order else None,
                    'order_date': order.date_order.isoformat() if order.date_order else None,
                    'merchant_id': order.partner_id.id,
                    'partner_id': order.partner_id.id,
                    'user_id': order.user_id.id,
                    'order_lines': lines,
                    'products': lines,
                    'amount_total': order.amount_total,
                }
                return self._json_response(data=result)
            else:
                orders = request.env['sale.order'].sudo().search(self._order_domain_for_user(auth_user))
                data = []
                for so in orders:
                    data.append({
                        'id': so.id,
                        'name': so.name,
                        'status': self._map_order_status_out(so.warehouse_status),
                        'warehouse_status': so.warehouse_status,
                        'merchant_id': so.partner_id.id,
                        'order_date': so.date_order.isoformat() if so.date_order else None,
                        'amount_total': so.amount_total,
                    })
                return self._json_response(data=data)
        else:
            if not self._can_create_orders(auth_user):
                return self._forbidden_response()
            # POST: create new order
            payload = self._parse_json_payload()
            if not payload:
                return self._json_response(error='Invalid JSON payload', status=400)
            partner_id = payload.get('merchant_id') or payload.get('partner_id')
            if not partner_id:
                return self._json_response(error='Missing merchant_id', status=400)
            partner = self._get_partner_by_id(int(partner_id))
            if not self._record_exists(partner):
                return self._json_response(error='Merchant not found', status=404)
            if not self._can_access_partner(auth_user, partner):
                return self._forbidden_response()
            explicit_user_id = payload.get('user_id')
            user_id = explicit_user_id or partner.user_id.id or auth_user.id
            assigned_user = self._get_user_by_id(int(user_id))
            if not self._record_exists(assigned_user):
                return self._json_response(error='Assigned user not found', status=404)
            if auth_user.is_api_delegate():
                if explicit_user_id and assigned_user.id != auth_user.id:
                    return self._forbidden_response()
                assigned_user = auth_user
            elif not self._can_assign_user(auth_user, assigned_user):
                return self._forbidden_response()
            order_date = payload.get('order_date')
            products = payload.get('products') or payload.get('lines')
            if not products:
                return self._json_response(error='Missing products list', status=400)
            order_vals = {
                'partner_id': partner.id,
                'user_id': assigned_user.id,
                'warehouse_status': 'draft',
            }
            if order_date:
                order_vals['date_order'] = order_date
            order = request.env['sale.order'].sudo().create(order_vals)
            for item in products:
                prod_id = item.get('product_id') or item.get('product_template_id') or item.get('template_id')
                if not prod_id:
                    return self._json_response(error='Missing product_id', status=400)
                qty = item.get('quantity') or item.get('qty') or 1.0
                price = item.get('price_unit')
                try:
                    product = self._get_product_by_any_id(prod_id)
                except Exception:
                    return self._json_response(error='Invalid product_id', status=400)
                if not self._record_exists(product):
                    return self._json_response(error='Product not found', status=404)
                line_vals = {
                    'order_id': order.id,
                    'product_id': product.id,
                    'product_uom_qty': float(qty),
                    'name': product.display_name,
                    'price_unit': price if price is not None else product.lst_price,
                }
                request.env['sale.order.line'].sudo().create(line_vals)
            # Optionally confirm the order
            status = payload.get('status')
            if status and status.lower() in ('confirmed', 'sale'):
                order.action_confirm()
            return self._json_response(data={
                'id': order.id,
                'name': order.name,
                'status': self._map_order_status_out(order.warehouse_status),
            })

    @http.route(['/orders/<int:order_id>', '/api/orders/<int:order_id>'],
                type='http', auth='public', methods=['PUT', 'DELETE'], csrf=False)
    def order_update_delete(self, order_id, **kwargs):
        auth_user = self._authenticate()
        if not auth_user:
            return self._json_response(error='Unauthorized', status=401)

        if request.httprequest.method == 'DELETE':
            if not (self._is_admin(auth_user) or self._user_has_rule(auth_user, 'orders', 'delete')):
                return self._forbidden_response()

        order = self._get_order_by_id(order_id)
        if not self._record_exists(order):
            return self._json_response(error='Order not found', status=404)
        if not order.sudo().search_count([('id', '=', order.id)] + self._order_domain_for_user(auth_user)):
            return self._forbidden_response()

        if request.httprequest.method == 'DELETE':
            order.sudo().unlink()
            return self._json_response(data={'message': 'Order deleted'})

        if not self._can_update_orders(auth_user):
            return self._forbidden_response()
        payload = self._parse_json_payload()
        if not payload:
            return self._json_response(error='Invalid JSON payload', status=400)
        vals = {}
        if 'merchant_id' in payload or 'partner_id' in payload:
            try:
                partner = self._get_partner_by_id(payload.get('merchant_id') or payload.get('partner_id'))
            except Exception:
                return self._json_response(error='Invalid merchant_id', status=400)
            if not self._record_exists(partner):
                return self._json_response(error='Merchant not found', status=404)
            if not self._can_access_partner(auth_user, partner):
                return self._forbidden_response()
            vals['partner_id'] = partner.id
        if 'order_date' in payload:
            vals['date_order'] = payload.get('order_date')
        status = payload.get('status')
        if status:
            mapped_status = self._map_order_status_in(status)
            current_status = order.warehouse_status or 'draft'
            if not self._is_valid_order_transition(current_status, mapped_status):
                return self._json_response(
                    error='Invalid status transition: %s -> %s' % (
                        self._map_order_status_out(current_status), self._map_order_status_out(mapped_status)
                    ),
                    status=400,
                )
            vals['warehouse_status'] = mapped_status
        if vals:
            order.sudo().write(vals)
        return self._json_response(data={
            'id': order.id,
            'status': self._map_order_status_out(order.warehouse_status),
            'warehouse_status': order.warehouse_status,
        })

    @http.route(['/inventory', '/api/inventory'], type='http', auth='public', methods=['GET', 'PUT'], csrf=False)
    def inventory(self, **kwargs):
        auth_user = self._authenticate()
        if not auth_user:
            return self._json_response(error='Unauthorized', status=401)
        if not self._is_warehouse(auth_user):
            return self._forbidden_response()

        if request.httprequest.method == 'GET':
            orders = request.env['sale.order'].sudo().search(self._order_domain_for_user(auth_user))
            data = []
            for so in orders:
                data.append({
                    'order_id': so.id,
                    'area': so.user_id.area_name or '',
                    'status': self._map_order_status_out(so.warehouse_status),
                })
            return self._json_response(data=data)

        payload = self._parse_json_payload()
        if not payload:
            return self._json_response(error='Invalid JSON payload', status=400)
        order_id = payload.get('order_id')
        status = payload.get('status')
        if not order_id or not status:
            return self._json_response(error='Missing order_id or status', status=400)
        status_map = {
            'pending': 'draft',
            'accepted': 'ready',
            'rejected': 'rejected',
            'prepared': 'prepared',
            'delivered': 'delivered',
        }
        mapped_status = status_map.get(str(status).strip().lower(), str(status).strip().lower())
        return self._update_order_status(order_id, mapped_status, reason=payload.get('reason'))

    # ---------------------------------------------------------------------
    # Payments & Wallet
    # ---------------------------------------------------------------------
    @http.route(['/api/payments'], type='http', auth='public', methods=['GET', 'POST'], csrf=False)
    def payments(self, **kwargs):
        """
        Record a customer payment. The JSON payload should contain
        ``invoice_id`` or ``partner_id``, ``amount`` and optionally
        ``payment_date`` and ``journal_id``. If ``invoice_id`` is supplied
        the payment will be reconciled against that invoice.
        """
        auth_user = self._authenticate()
        if not auth_user:
            return self._json_response(error='Unauthorized', status=401)
        if request.httprequest.method == 'GET':
            user, error_response = self._get_requested_user(auth_user)
            if error_response:
                return error_response
            date_str = request.params.get('date')
            domain = self._payment_domain_for_user(auth_user, user)
            if date_str:
                try:
                    date = fields.Date.from_string(date_str)
                except Exception:
                    return self._json_response(error='Invalid date format (expected YYYY-MM-DD)', status=400)
                start = datetime.combine(date, time.min)
                end = datetime.combine(date, time.max)
                domain += [('create_date', '>=', start), ('create_date', '<=', end)]
            payments = request.env['account.payment'].sudo().search(domain, order='create_date desc')
            data = []
            for payment in payments:
                data.append({
                    'id': payment.id,
                    'partner_id': payment.partner_id.id,
                    'partner_name': payment.partner_id.display_name,
                    'amount': payment.amount,
                    'date': payment.date.isoformat() if payment.date else None,
                    'journal_id': payment.journal_id.id,
                    'create_uid': payment.create_uid.id,
                })
            return self._json_response(data=data)

        if not self._can_create_sales_docs(auth_user):
            return self._forbidden_response()
        payload = self._parse_json_payload()
        if not payload:
            return self._json_response(error='Invalid JSON payload', status=400)
        amount = payload.get('amount')
        invoice_id = payload.get('invoice_id')
        partner_id = payload.get('partner_id')
        if not amount:
            return self._json_response(error='Missing amount', status=400)
        try:
            amount = float(amount)
        except Exception:
            return self._json_response(error='Invalid amount', status=400)
        journal_id = payload.get('journal_id')
        journal = None
        if journal_id:
            journal = request.env['account.journal'].sudo().browse(int(journal_id)).exists()
        if not journal:
            journal = request.env['account.journal'].sudo().search([
                ('type', 'in', ('bank', 'cash')),
                ('company_id', '=', auth_user.company_id.id)
            ], limit=1)
        if invoice_id:
            invoice = self._get_invoice_by_id(int(invoice_id))
            if not self._record_exists(invoice):
                return self._json_response(error='Invoice not found', status=404)
            if not request.env['account.move'].sudo().search_count([
                ('id', '=', invoice.id)
            ] + self._invoice_domain_for_user(auth_user)):
                return self._forbidden_response()
            partner = invoice.partner_id
        elif partner_id:
            partner = self._get_partner_by_id(int(partner_id))
            if not self._record_exists(partner):
                return self._json_response(error='Merchant not found', status=404)
            if not self._can_access_partner(auth_user, partner):
                return self._forbidden_response()
        else:
            return self._json_response(error='Missing invoice_id or partner_id', status=400)
        payment_date = payload.get('payment_date') or fields.Date.today()
        payment_vals = {
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'partner_id': partner.id,
            'amount': amount,
            'journal_id': journal.id,
            'date': payment_date,
        }
        payment = request.env['account.payment'].sudo().create(payment_vals)
        try:
            payment.action_post()
            if invoice_id:
                payment_line = payment.line_ids.filtered(lambda l: l.account_id.user_type_id.type in ('receivable', 'payable'))
                invoice_line = invoice.line_ids.filtered(lambda l: l.account_id.user_type_id.type in ('receivable', 'payable'))
                (payment_line + invoice_line).reconcile()
        except Exception as e:
            _logger.exception('Failed to post or reconcile payment: %s', e)
        return self._json_response(data={'id': payment.id})

    @http.route(['/api/wallet_summary'], type='http', auth='public', methods=['GET'], csrf=False)
    def wallet_summary(self, **kwargs):
        """
        Return a summary of payments collected by a delivery user on a given
        date. Query parameters: ``user_id`` (defaults to the authenticated
        user) and ``date`` (defaults to today). The response includes the
        total amount collected and the number of payments recorded.
        """
        auth_user = self._authenticate()
        if not auth_user:
            return self._json_response(error='Unauthorized', status=401)
        date_str = request.params.get('date')
        user, error_response = self._get_requested_user(auth_user)
        if error_response:
            return error_response
        if date_str:
            try:
                date = fields.Date.from_string(date_str)
            except Exception:
                return self._json_response(error='Invalid date format (expected YYYY-MM-DD)', status=400)
        else:
            date = fields.Date.today()
        start = datetime.combine(date, time.min)
        end = datetime.combine(date, time.max)
        payments = request.env['account.payment'].sudo().search(
            self._payment_domain_for_user(auth_user, user) + [
                ('create_date', '>=', start),
                ('create_date', '<=', end),
            ]
        )
        total = sum(pay.amount for pay in payments)
        return self._json_response(data={
            'user_id': user.id,
            'date': str(date),
            'payments_count': len(payments),
            'total_collected': total,
        })

    # ---------------------------------------------------------------------
    # Invoices
    # ---------------------------------------------------------------------
    @http.route(['/api/invoices', '/api/invoices/<int:invoice_id>', '/invoices', '/invoices/<int:invoice_id>'],
                type='http', auth='public', methods=['GET', 'POST'], csrf=False)
    def invoices(self, invoice_id=None, **kwargs):
        """
        GET /api/invoices                -> list invoices for the authenticated user
        GET /api/invoices/<id>           -> retrieve a single invoice
        POST /api/invoices               -> create a new customer invoice
        """
        auth_user = self._authenticate()
        if not auth_user:
            return self._json_response(error='Unauthorized', status=401)
        if not self._can_manage_invoices(auth_user):
            return self._forbidden_response()
        if request.httprequest.method == 'GET':
            if invoice_id:
                inv = self._get_invoice_by_id(invoice_id)
                if not self._record_exists(inv):
                    return self._json_response(error='Invoice not found', status=404)
                if not request.env['account.move'].sudo().search_count([
                    ('id', '=', inv.id)
                ] + self._invoice_domain_for_user(auth_user)):
                    return self._forbidden_response()
                lines = []
                for line in inv.invoice_line_ids:
                    lines.append({
                        'product_id': line.product_id.id,
                        'product_name': line.product_id.display_name,
                        'quantity': line.quantity,
                        'price_unit': line.price_unit,
                        'subtotal': line.price_subtotal,
                    })
                result = self._serialize_invoice_summary(inv)
                result.update({
                    'invoice_date': inv.invoice_date.isoformat() if inv.invoice_date else None,
                    'order_id': self._invoice_order_id(inv),
                    'merchant_id': inv.partner_id.id,
                    'payment_method': self._invoice_payment_method(inv),
                    'invoice_lines': lines,
                    'products': lines,
                })
                return self._json_response(data=result)
            else:
                invoices = request.env['account.move'].sudo().search(self._invoice_domain_for_user(auth_user))
                data = []
                for inv in invoices:
                    lines = []
                    for line in inv.invoice_line_ids:
                        lines.append({
                            'product_id': line.product_id.id,
                            'quantity': line.quantity,
                            'price_unit': line.price_unit,
                            'subtotal': line.price_subtotal,
                        })
                    row = self._serialize_invoice_summary(inv)
                    row.update({
                        'order_id': self._invoice_order_id(inv),
                        'merchant_id': inv.partner_id.id,
                        'payment_method': self._invoice_payment_method(inv),
                        'products': lines,
                    })
                    data.append(row)
                return self._json_response(data=data)
        else:
            payload = self._parse_json_payload()
            if not payload:
                return self._json_response(error='Invalid JSON payload', status=400)
            partner_id = payload.get('merchant_id') or payload.get('partner_id')
            if not partner_id:
                return self._json_response(error='Missing merchant_id', status=400)
            partner = self._get_partner_by_id(int(partner_id))
            if not self._record_exists(partner):
                return self._json_response(error='Merchant not found', status=404)
            if not self._can_access_partner(auth_user, partner):
                return self._forbidden_response()
            order_id = payload.get('order_id')
            order = None
            if order_id:
                try:
                    order = self._get_order_by_id(int(order_id))
                except Exception:
                    return self._json_response(error='Invalid order_id', status=400)
                if not self._record_exists(order):
                    return self._json_response(error='Order not found', status=404)
                if order.partner_id.id != partner.id:
                    return self._json_response(error='order_id does not belong to merchant_id', status=400)
                if not order.sudo().search_count([('id', '=', order.id)] + self._order_domain_for_user(auth_user)):
                    return self._forbidden_response()
            invoice_date = payload.get('invoice_date')
            invoice_user_id = payload.get('user_id') or auth_user.id
            invoice_user = self._get_user_by_id(int(invoice_user_id))
            if not self._record_exists(invoice_user) or invoice_user.id != auth_user.id:
                return self._forbidden_response()
            payment_method = payload.get('payment_method')
            lines = payload.get('products') or payload.get('lines')
            if not lines:
                return self._json_response(error='Missing products list', status=400)
            inv_vals = {
                'move_type': 'out_invoice',
                'partner_id': partner.id,
                'invoice_date': invoice_date,
                'invoice_user_id': invoice_user.id,
                'invoice_origin': order.name if order else False,
            }
            if payment_method:
                move_fields = request.env['account.move']._fields
                if 'invoice_payment_ref' in move_fields:
                    inv_vals['invoice_payment_ref'] = payment_method
                elif 'payment_reference' in move_fields:
                    inv_vals['payment_reference'] = payment_method
                elif 'ref' in move_fields:
                    inv_vals['ref'] = payment_method
            invoice = request.env['account.move'].sudo().create(inv_vals)
            for item in lines:
                product = request.env['product.product'].sudo().browse(int(item.get('product_id'))).exists()
                if not self._record_exists(product):
                    return self._json_response(error='Product not found', status=404)
                qty = float(item.get('quantity') or 1.0)
                price = item.get('price_unit') or product.lst_price
                tax_ids = product.taxes_id.filtered(lambda t: t.type_tax_use in ('sale', 'all')).ids
                line_vals = {
                    'move_id': invoice.id,
                    'product_id': product.id,
                    'name': product.display_name,
                    'quantity': qty,
                    'price_unit': price,
                    'tax_ids': [(6, 0, tax_ids)],
                }
                request.env['account.move.line'].sudo().create(line_vals)
            # Post the invoice (moves it from draft to posted)
            try:
                invoice.action_post()
            except Exception as e:
                _logger.exception('Failed to post invoice: %s', e)
            return self._json_response(data={
                'id': invoice.id,
                'name': invoice.name,
                'order_id': self._invoice_order_id(invoice),
                'merchant_id': invoice.partner_id.id,
                'payment_method': self._invoice_payment_method(invoice),
                'products': [{
                    'product_id': line.product_id.id,
                    'quantity': line.quantity,
                    'price_unit': line.price_unit,
                    'subtotal': line.price_subtotal,
                } for line in invoice.invoice_line_ids],
            })

    # ---------------------------------------------------------------------
    # Sale Order Warehouse Status Endpoints
    # ---------------------------------------------------------------------
    def _update_order_status(self, order_id, new_status, reason=None):
        """
        Internal helper to set the ``warehouse_status`` on a sale order and
        optionally record a rejection reason. Returns a JSON response.
        """
        auth_user = self._authenticate()
        if not auth_user:
            return self._json_response(error='Unauthorized', status=401)
        if not self._is_warehouse(auth_user):
            return self._forbidden_response()
        order = self._get_order_by_id(int(order_id))
        if not self._record_exists(order):
            return self._json_response(error='Order not found', status=404)
        vals = {'warehouse_status': new_status}
        if reason:
            vals['rejection_reason'] = reason
        order.write(vals)
        return self._json_response(data={'id': order.id, 'warehouse_status': order.warehouse_status})

    @http.route(['/api/sale_orders/<int:order_id>/prepare'], type='http', auth='public', methods=['POST'], csrf=False)
    def order_prepare(self, order_id, **kwargs):
        """Mark a sale order as prepared (warehouse picked)."""
        return self._update_order_status(order_id, 'prepared')

    @http.route(['/api/sale_orders/<int:order_id>/deliver'], type='http', auth='public', methods=['POST'], csrf=False)
    def order_deliver(self, order_id, **kwargs):
        """Mark a sale order as delivered (handed to customer)."""
        return self._update_order_status(order_id, 'delivered')

    @http.route(['/api/sale_orders/<int:order_id>/reject'], type='http', auth='public', methods=['POST'], csrf=False)
    def order_reject(self, order_id, **kwargs):
        """Reject a sale order with a reason provided in the JSON payload."""
        try:
            payload = json.loads(request.httprequest.data or '{}')
        except Exception:
            return self._json_response(error='Invalid JSON payload', status=400)
        reason = payload.get('reason')
        if not reason:
            return self._json_response(error='Missing reason', status=400)
        return self._update_order_status(order_id, 'rejected', reason=reason)

    @http.route(['/api/sale_orders/<int:order_id>/ready'], type='http', auth='public', methods=['POST'], csrf=False)
    def order_ready(self, order_id, **kwargs):
        """Mark a sale order as ready for pickup by the customer."""
        return self._update_order_status(order_id, 'ready')

    @http.route(['/api/sale_orders/<int:order_id>/handover'], type='http', auth='public', methods=['POST'], csrf=False)
    def order_handover(self, order_id, **kwargs):
        """Mark a sale order as handed over to the delivery person or customer."""
        return self._update_order_status(order_id, 'handover')

    # ---------------------------------------------------------------------
    # Credit Notes (Return Invoices)
    # ---------------------------------------------------------------------
    @http.route([
        '/api/returns', '/api/returns/<int:return_id>',
        '/return-invoices', '/return-invoices/<int:return_id>',
        '/api/return-invoices', '/api/return-invoices/<int:return_id>',
    ], type='http', auth='public', methods=['GET', 'POST'], csrf=False)
    def returns(self, return_id=None, **kwargs):
        """
        Create a credit note (refund) for an existing invoice. The payload
        must include the ``invoice_id`` of the original invoice and at
        least one line with a product and quantity to return.
        """
        auth_user = self._authenticate()
        if not auth_user:
            return self._json_response(error='Unauthorized', status=401)
        if not (auth_user.is_api_delegate() or self._user_has_rule(auth_user, 'returns', self._http_action())):
            return self._forbidden_response()
        if request.httprequest.method == 'GET':
            domain = self._invoice_domain_for_user(auth_user, move_type='out_refund')
            if return_id:
                domain += [('id', '=', return_id)]
            refunds = request.env['account.move'].sudo().search(domain, order='invoice_date desc, id desc')
            if return_id and not refunds:
                return self._json_response(error='Return invoice not found', status=404)
            data = []
            for refund in refunds:
                products = []
                for line in refund.invoice_line_ids:
                    products.append({
                        'product_id': line.product_id.id,
                        'quantity': line.quantity,
                        'price_unit': abs(line.price_unit),
                        'subtotal': abs(line.price_subtotal),
                    })
                row = self._serialize_invoice_summary(refund)
                row.update({
                    'invoice_id': refund.reversed_entry_id.id if refund.reversed_entry_id else None,
                    'products': products,
                    'note': refund.narration or '',
                })
                data.append(row)
            return self._json_response(data=data[0] if return_id else data)

        payload = self._parse_json_payload()
        if not payload:
            return self._json_response(error='Invalid JSON payload', status=400)
        invoice_id = payload.get('invoice_id') or payload.get('original_invoice_id')
        if not invoice_id:
            return self._json_response(error='Missing invoice_id', status=400)
        invoice = self._get_invoice_by_id(int(invoice_id))
        if not self._record_exists(invoice) or invoice.move_type != 'out_invoice':
            return self._json_response(error='Invalid invoice for refund', status=400)
        if not request.env['account.move'].sudo().search_count([
            ('id', '=', invoice.id)
        ] + self._invoice_domain_for_user(auth_user)):
            return self._forbidden_response()
        lines = payload.get('products') or payload.get('lines')
        if not lines:
            return self._json_response(error='Missing return lines', status=400)
        note = payload.get('note') or payload.get('reason') or ''
        credit_vals = {
            'move_type': 'out_refund',
            'partner_id': invoice.partner_id.id,
            'invoice_origin': invoice.name,
            'reversed_entry_id': invoice.id,
            'invoice_user_id': invoice.invoice_user_id.id,
            'narration': note or False,
        }
        credit = request.env['account.move'].sudo().create(credit_vals)
        for item in lines:
            product = request.env['product.product'].sudo().browse(int(item.get('product_id'))).exists()
            if not self._record_exists(product):
                return self._json_response(error='Product not found', status=404)
            qty = float(item.get('quantity') or 1.0)
            line_note = item.get('note') or item.get('reason') or note
            line_vals = {
                'move_id': credit.id,
                'product_id': product.id,
                'name': line_note or _('Return of %s') % product.display_name,
                'quantity': qty,
                'price_unit': -(item.get('price_unit') or product.lst_price),
                'tax_ids': [(6, 0, product.taxes_id.ids)],
            }
            request.env['account.move.line'].sudo().create(line_vals)
        try:
            credit.action_post()
        except Exception as e:
            _logger.exception('Failed to post credit note: %s', e)
        return self._json_response(data={
            'id': credit.id,
            'name': credit.name,
            'invoice_id': credit.reversed_entry_id.id if credit.reversed_entry_id else invoice.id,
            'products': [{
                'product_id': line.product_id.id,
                'quantity': line.quantity,
                'price_unit': abs(line.price_unit),
                'subtotal': abs(line.price_subtotal),
            } for line in credit.invoice_line_ids],
            'note': credit.narration or note,
        })

    @http.route(['/api/admin/users', '/api/admin/users/<int:user_id>'], type='http', auth='public', methods=['GET', 'POST'], csrf=False)
    def admin_users(self, user_id=None, **kwargs):
        auth_user = self._authenticate()
        if not auth_user:
            return self._json_response(error='Unauthorized', status=401)
        if not self._is_admin(auth_user):
            return self._forbidden_response()

        Users = request.env['res.users'].sudo()
        if request.httprequest.method == 'GET':
            domain = [('share', '=', False)]
            if user_id:
                domain.append(('id', '=', user_id))
            users = Users.search(domain)
            if user_id and not users:
                return self._json_response(error='User not found', status=404)
            data = [self._serialize_user(user) for user in users]
            return self._json_response(data=data[0] if user_id else data)

        payload = self._parse_json_payload()
        if not payload:
            return self._json_response(error='Invalid JSON payload', status=400)
        if not user_id:
            return self._json_response(error='Missing user_id in route', status=400)
        user = Users.browse(user_id).exists()
        if not user:
            return self._json_response(error='User not found', status=404)

        vals = {}
        if 'area_name' in payload:
            vals['area_name'] = payload.get('area_name') or False
        if 'supervisor_id' in payload:
            supervisor_id = payload.get('supervisor_id')
            if supervisor_id:
                supervisor = Users.browse(int(supervisor_id)).exists()
                if not supervisor:
                    return self._json_response(error='Supervisor not found', status=404)
                vals['supervisor_id'] = supervisor.id
            else:
                vals['supervisor_id'] = False
        if vals:
            user.write(vals)

        if 'roles' in payload:
            roles = payload.get('roles') or []
            if not isinstance(roles, list) or not all(role in self.ROLE_GROUP_MAP for role in roles):
                return self._json_response(error='Invalid roles list', status=400)
            self._set_user_roles(user, roles)

        return self._json_response(data=self._serialize_user(user))

    @http.route(['/api/signup_requests', '/api/signup_requests/<int:request_id>'], type='http', auth='public', methods=['GET'], csrf=False)
    def signup_requests(self, request_id=None, **kwargs):
        auth_user = self._authenticate()
        if not auth_user:
            return self._json_response(error='Unauthorized', status=401)
        if not self._is_admin(auth_user):
            return self._forbidden_response()
        domain = []
        state = request.params.get('state')
        if state:
            domain.append(('state', '=', state))
        if request_id:
            domain.append(('id', '=', request_id))
        signup_requests = request.env['api.signup.request'].sudo().search(domain, order='create_date desc, id desc')
        if request_id and not signup_requests:
            return self._json_response(error='Signup request not found', status=404)
        data = [self._serialize_signup_request(signup_request) for signup_request in signup_requests]
        return self._json_response(data=data[0] if request_id else data)

    @http.route(['/api/signup_requests/<int:request_id>/approve'], type='http', auth='public', methods=['POST'], csrf=False)
    def approve_signup_request(self, request_id, **kwargs):
        auth_user = self._authenticate()
        if not auth_user:
            return self._json_response(error='Unauthorized', status=401)
        if not self._is_admin(auth_user):
            return self._forbidden_response()
        signup_request = self._get_signup_request_by_id(request_id)
        if not signup_request:
            return self._json_response(error='Signup request not found', status=404)
        if signup_request.state != 'pending':
            return self._json_response(error='Signup request is not pending', status=400)
        created_user, error_response = self._create_user_from_signup_request(signup_request, auth_user)
        if error_response:
            return error_response
        return self._json_response(data={
            'signup_request': self._serialize_signup_request(signup_request),
            'user': self._serialize_user(created_user),
        })

    @http.route(['/api/signup_requests/<int:request_id>/reject'], type='http', auth='public', methods=['POST'], csrf=False)
    def reject_signup_request(self, request_id, **kwargs):
        auth_user = self._authenticate()
        if not auth_user:
            return self._json_response(error='Unauthorized', status=401)
        if not self._is_admin(auth_user):
            return self._forbidden_response()
        signup_request = self._get_signup_request_by_id(request_id)
        if not signup_request:
            return self._json_response(error='Signup request not found', status=404)
        if signup_request.state != 'pending':
            return self._json_response(error='Signup request is not pending', status=400)
        payload = self._parse_json_payload() or {}
        signup_request.sudo().write({
            'state': 'rejected',
            'reviewed_at': fields.Datetime.now(),
            'reviewed_by_id': auth_user.id,
            'reject_reason': payload.get('reason') or False,
        })
        return self._json_response(data=self._serialize_signup_request(signup_request))

    # ---------------------------------------------------------------------
    # Merchant Visits
    # ---------------------------------------------------------------------
    @http.route(['/api/merchant_visits'], type='http', auth='public', methods=['GET', 'POST'], csrf=False)
    def merchant_visits(self, **kwargs):
        """
        GET: Retrieve visit records for a user on a specific date. Query
        parameters: ``user_id`` and ``date`` (YYYY-MM-DD). If omitted, the
        authenticated user and today are used.

        POST: Create a new merchant visit. The JSON payload must contain
        ``user_id``, ``merchant_id`` and optionally ``visit_datetime`` and
        ``notes``.
        """
        auth_user = self._authenticate()
        if not auth_user:
            return self._json_response(error='Unauthorized', status=401)
        # Handle GET
        if request.httprequest.method == 'GET':
            date_str = request.params.get('date')
            user, error_response = self._get_requested_user(auth_user)
            if error_response:
                return error_response
            if date_str:
                try:
                    date = fields.Date.from_string(date_str)
                except Exception:
                    return self._json_response(error='Invalid date format (expected YYYY-MM-DD)', status=400)
            else:
                date = fields.Date.today()
            start = datetime.combine(date, time.min)
            end = datetime.combine(date, time.max)
            visits = request.env['merchant.visit'].sudo().search([
                ('user_id', '=', user.id),
                ('visit_datetime', '>=', start),
                ('visit_datetime', '<=', end),
            ])
            data = []
            for visit in visits:
                data.append({
                    'id': visit.id,
                    'user_id': visit.user_id.id,
                    'merchant_id': visit.partner_id.id,
                    'merchant_name': visit.partner_id.display_name,
                    'visit_datetime': visit.visit_datetime.isoformat(),
                    'notes': visit.notes or '',
                })
            return self._json_response(data=data)
        # Handle POST
        payload = self._parse_json_payload()
        if not payload:
            return self._json_response(error='Invalid JSON payload', status=400)
        user_id = payload.get('user_id')
        merchant_id = payload.get('merchant_id') or payload.get('partner_id')
        if not all([user_id, merchant_id]):
            return self._json_response(error='Missing user_id or merchant_id', status=400)
        try:
            user = self._get_user_by_id(int(user_id))
            partner = self._get_partner_by_id(int(merchant_id))
        except Exception:
            return self._json_response(error='Invalid user_id or merchant_id', status=400)
        if not self._record_exists(user) or not self._record_exists(partner):
            return self._json_response(error='User or merchant not found', status=404)
        if not self._can_manage_user(auth_user, user):
            return self._forbidden_response()
        if not self._can_access_partner(auth_user, partner):
            return self._forbidden_response()
        visit_datetime = payload.get('visit_datetime')
        if visit_datetime:
            try:
                visit_dt = fields.Datetime.from_string(visit_datetime)
            except Exception:
                return self._json_response(error='Invalid visit_datetime format', status=400)
        else:
            visit_dt = fields.Datetime.now()
        notes = payload.get('notes') or ''
        visit = request.env['merchant.visit'].sudo().create({
            'user_id': user.id,
            'partner_id': partner.id,
            'visit_datetime': visit_dt,
            'notes': notes,
        })
        return self._json_response(data={'id': visit.id})

    @http.route(['/itineraries', '/api/itineraries'], type='http', auth='public', methods=['GET'], csrf=False)
    def itineraries(self, **kwargs):
        auth_user = self._authenticate()
        if not auth_user:
            return self._json_response(error='Unauthorized', status=401)
        if not self._can_access_itineraries(auth_user):
            return self._forbidden_response()
        delivery_id = request.params.get('delivery_id') or request.params.get('user_id') or auth_user.id
        try:
            delivery_user = self._get_user_by_id(int(delivery_id))
        except Exception:
            return self._json_response(error='Invalid delivery_id', status=400)
        if not self._record_exists(delivery_user):
            return self._json_response(error='Delivery user not found', status=404)
        if not self._can_manage_user(auth_user, delivery_user):
            return self._forbidden_response()
        date_str = request.params.get('date')
        if date_str:
            try:
                itinerary_date = fields.Date.from_string(date_str)
            except Exception:
                return self._json_response(error='Invalid date format (expected YYYY-MM-DD)', status=400)
        else:
            itinerary_date = fields.Date.today()
        start = datetime.combine(itinerary_date, time.min)
        end = datetime.combine(itinerary_date, time.max)
        visits = request.env['merchant.visit'].sudo().search([
            ('user_id', '=', delivery_user.id),
            ('visit_datetime', '>=', start),
            ('visit_datetime', '<=', end),
        ], order='visit_datetime asc')
        merchant_locations = []
        for visit in visits:
            merchant_locations.append({
                'merchant_id': visit.partner_id.id,
                'merchant_name': visit.partner_id.display_name,
                'address': visit.partner_id.contact_address or '',
                'gps_latitude': visit.partner_id.partner_latitude or 0.0,
                'gps_longitude': visit.partner_id.partner_longitude or 0.0,
            })
        return self._json_response(data={
            'delivery_id': delivery_user.id,
            'date': str(itinerary_date),
            'merchant_locations': merchant_locations,
        })

    @http.route(['/custody-funds', '/api/custody-funds'], type='http', auth='public', methods=['GET', 'POST'], csrf=False)
    def custody_funds(self, **kwargs):
        auth_user = self._authenticate()
        if not auth_user:
            return self._json_response(error='Unauthorized', status=401)
        if not (auth_user.is_api_delegate() or self._user_has_rule(auth_user, 'payments', self._http_action())):
            return self._forbidden_response()

        if request.httprequest.method == 'GET':
            delivery_id = request.params.get('delivery_id') or request.params.get('user_id') or auth_user.id
            try:
                delivery_user = self._get_user_by_id(int(delivery_id))
            except Exception:
                return self._json_response(error='Invalid delivery_id', status=400)
            if not self._record_exists(delivery_user):
                return self._json_response(error='Delivery user not found', status=404)
            if delivery_user.id != auth_user.id:
                return self._forbidden_response()
            date_str = request.params.get('date')
            if date_str:
                try:
                    target_date = fields.Date.from_string(date_str)
                except Exception:
                    return self._json_response(error='Invalid date format (expected YYYY-MM-DD)', status=400)
            else:
                target_date = fields.Date.today()
            start = datetime.combine(target_date, time.min)
            end = datetime.combine(target_date, time.max)
            payments = request.env['account.payment'].sudo().search([
                ('partner_type', '=', 'customer'),
                ('state', '=', 'posted'),
                ('create_uid', '=', delivery_user.id),
                ('create_date', '>=', start),
                ('create_date', '<=', end),
            ])
            return self._json_response(data={
                'delivery_id': delivery_user.id,
                'date': str(target_date),
                'collected_amount': sum(pay.amount for pay in payments),
            })

        payload = self._parse_json_payload()
        if not payload:
            return self._json_response(error='Invalid JSON payload', status=400)
        delivery_id = payload.get('delivery_id') or auth_user.id
        collected_amount = payload.get('collected_amount') or payload.get('amount')
        partner_id = payload.get('partner_id')
        if not collected_amount:
            return self._json_response(error='Missing collected_amount', status=400)
        try:
            delivery_user = self._get_user_by_id(int(delivery_id))
            amount = float(collected_amount)
        except Exception:
            return self._json_response(error='Invalid delivery_id or collected_amount', status=400)
        if not self._record_exists(delivery_user):
            return self._json_response(error='Delivery user not found', status=404)
        if delivery_user.id != auth_user.id:
            return self._forbidden_response()
        if not partner_id:
            return self._json_response(error='Missing partner_id', status=400)
        partner = self._get_partner_by_id(int(partner_id))
        if not self._record_exists(partner):
            return self._json_response(error='Merchant not found', status=404)
        journal = request.env['account.journal'].sudo().search([
            ('type', 'in', ('bank', 'cash')),
            ('company_id', '=', auth_user.company_id.id)
        ], limit=1)
        if not journal:
            return self._json_response(error='No payment journal configured', status=400)
        payment = request.env['account.payment'].sudo().with_user(delivery_user).create({
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'partner_id': partner.id,
            'amount': amount,
            'journal_id': journal.id,
            'date': payload.get('date') or fields.Date.today(),
        })
        payment.action_post()
        return self._json_response(data={
            'delivery_id': delivery_user.id,
            'collected_amount': payment.amount,
            'date': str(payment.date),
        }, status=201)

    # ---------------------------------------------------------------------
    # Offers & Promotions (read‑only)
    # ---------------------------------------------------------------------
    @http.route(['/api/offers'], type='http', auth='public', methods=['GET'], csrf=False)
    def offers(self, **kwargs):
        """
        Return active price lists (offers) with their validity dates and
        discount rules. This endpoint is optional and can be customized to
        return promotions stored in a custom model instead of pricelists.
        """
        auth_user = self._authenticate()
        if not auth_user:
            return self._json_response(error='Unauthorized', status=401)
        if not self._can_create_sales_docs(auth_user):
            return self._forbidden_response()
        pricelists = request.env['product.pricelist'].sudo().search([
            ('active', '=', True)
        ])
        data = []
        for pl in pricelists:
            items = []
            for item in pl.item_ids:
                items.append({
                    'product_id': item.product_id.id if item.product_id else None,
                    'min_quantity': item.min_quantity,
                    'applied_on': item.applied_on,
                    'fixed_price': item.fixed_price,
                    'percent_price': item.percent_price,
                    'date_start': item.date_start.isoformat() if item.date_start else None,
                    'date_end': item.date_end.isoformat() if item.date_end else None,
                })
            data.append({
                'id': pl.id,
                'name': pl.name,
                'currency_id': pl.currency_id.id,
                'items': items,
            })
        return self._json_response(data=data)

    # ---------------------------------------------------------------------
    # Invoice PDF Upload
    # ---------------------------------------------------------------------
    @http.route(['/api/invoices/<int:invoice_id>/upload_pdf'], type='http', auth='public', methods=['POST'], csrf=False)
    def invoice_upload_pdf(self, invoice_id, **kwargs):
        """
        Attach a PDF file to an invoice record. The file can be supplied
        either as a multipart/form-data upload under the ``file`` field or
        encoded in JSON as a base64 string under the ``pdf`` key.
        """
        auth_user = self._authenticate()
        if not auth_user:
            return self._json_response(error='Unauthorized', status=401)
        invoice = self._get_invoice_by_id(invoice_id)
        if not self._record_exists(invoice):
            return self._json_response(error='Invoice not found', status=404)
        if not request.env['account.move'].sudo().search_count([
            ('id', '=', invoice.id)
        ] + self._invoice_domain_for_user(auth_user)):
            return self._forbidden_response()
        data = None
        file_name = 'invoice_%s.pdf' % invoice.name
        # Check for multipart/form-data
        if request.httprequest.files:
            file_storage = request.httprequest.files.get('file') or request.httprequest.files.get('pdf')
            if not file_storage:
                return self._json_response(error='No file part in request', status=400)
            file_name = file_storage.filename or file_name
            data = base64.b64encode(file_storage.read()).decode('ascii')
        else:
            # JSON payload base64
            try:
                payload = json.loads(request.httprequest.data or '{}')
            except Exception:
                return self._json_response(error='Invalid JSON payload', status=400)
            pdf_b64 = payload.get('pdf') or payload.get('file')
            if not pdf_b64:
                return self._json_response(error='Missing pdf data', status=400)
            data = pdf_b64
            file_name = payload.get('filename') or file_name
        if not data:
            return self._json_response(error='No PDF data supplied', status=400)
        # Create attachment
        request.env['ir.attachment'].sudo().create({
            'name': file_name,
            'res_model': 'account.move',
            'res_id': invoice.id,
            'type': 'binary',
            'datas': data,
            'mimetype': 'application/pdf',
        })
        return self._json_response(data={'message': 'PDF attached successfully'})

    # ---------------------------------------------------------------------
    # API Rules Management
    # ---------------------------------------------------------------------
    @http.route(['/api/rules'], type='http', auth='public', methods=['GET', 'POST'], csrf=False)
    def api_rules(self, **kwargs):
        ALLOWED_RESOURCES = {
            # ---------------- SALES & POS ----------------
            'orders': {
                'create', 'read', 'update', 'delete',
                'confirm', 'cancel', 'hold', 'print', 'lock', 'unlock'
            },
            'pos_orders': {
                'create', 'read', 'update', 'delete',
                'pay', 'refund', 'cancel', 'print_receipt', 'close_session'
            },

            # ---------------- ACCOUNTING ----------------
            'invoices': {
                'create', 'read', 'update', 'delete',
                'post', 'validate', 'cancel', 'pay', 'refund', 'print', 'send_email'
            },
            'payments': {
                'create', 'read', 'update', 'delete',
                'post', 'validate', 'cancel', 'reconcile', 'reject'
            },
            'journal_entries': {
                'create', 'read', 'update', 'delete',
                'post', 'reverse', 'cancel'
            },

            # ---------------- INVENTORY & LOGISTICS ----------------
            'inventory': {
                'create', 'read', 'update', 'delete',
                'validate', 'transfer', 'scrap', 'adjust', 'reserve', 'release'
            },
            'stock_moves': {
                'create', 'read', 'update', 'delete',
                'validate', 'cancel', 'assign'
            },
            'deliveries': {
                'create', 'read', 'update', 'delete',
                'dispatch', 'deliver', 'cancel', 'track', 'print_label'
            },

            # ---------------- PURCHASING & RETURNS ----------------
            'purchase_orders': {
                'create', 'read', 'update', 'delete',
                'confirm', 'approve', 'cancel', 'receive', 'create_bill'
            },
            'returns': {
                'create', 'read', 'update', 'delete',
                'approve', 'reject', 'receive', 'process_refund'
            },

            # ---------------- PRODUCTS & CONTACTS ----------------
            'products': {
                'create', 'read', 'update', 'delete',
                'archive', 'unarchive', 'update_price', 'update_stock'
            },
            'customers': {
                'create', 'read', 'update', 'delete',
                'archive', 'unarchive', 'merge', 'set_credit_limit'
            },
            'merchants': {
                'create', 'read', 'update', 'delete',
                'approve', 'suspend', 'activate', 'deactivate'
            },

            # ---------------- CRM & LEADS ----------------
            'leads': {
                'create', 'read', 'update', 'delete',
                'convert', 'assign', 'qualify', 'close_lost', 'close_won'
            },

            # ---------------- HR & EMPLOYEES ----------------
            'employees': {
                'create', 'read', 'update', 'delete',
                'activate', 'deactivate', 'assign_manager', 'update_contract'
            },

            # ---------------- SYSTEM & FILES ----------------
            'users': {
                'create', 'read', 'update', 'delete',
                'activate', 'deactivate', 'reset_password', 'assign_role'
            },
            'attachments': {
                'create', 'read', 'delete', 'download', 'upload'
            },
            'reports': {
                'read', 'export_excel', 'export_pdf', 'print'
            }
        }
        auth_user = self._authenticate()
        if not auth_user:
            return self._json_response(error='Unauthorized', status=401)

        # -------------------- GET --------------------
        if request.httprequest.method == 'GET':
            try:
                rules = request.env['api.rules'].sudo().search([])
                data = [{
                    'id': r.id,
                    'name': r.name,
                    'operations': r.operations
                } for r in rules]
                return self._json_response(data=data)
            except Exception as e:
                return self._json_response(
                    error='Failed to retrieve rules: %s' % str(e),
                    status=500
                )

        # -------------------- POST --------------------
        payload = self._parse_json_payload()
        if not payload:
            return self._json_response(error='Invalid JSON payload', status=400)

        name = payload.get('name')
        if not name:
            return self._json_response(error='Missing rule name', status=400)

        operations = payload.get('operations')

        if not isinstance(operations, dict):
            return self._json_response(
                error='operations must be a dictionary',
                status=400
            )

        for resource, actions in operations.items():

            if resource not in ALLOWED_RESOURCES:
                allowed_list = ", ".join(ALLOWED_RESOURCES.keys())
                return self._json_response(
                    error=f'Invalid resource: {resource}. Available resources are: {allowed_list}',
                    status=400
                )

            if not isinstance(actions, list):
                return self._json_response(
                    error=f'Actions for {resource} must be a list',
                    status=400
                )

            invalid_actions = [
                act for act in actions
                if act not in ALLOWED_RESOURCES[resource]
            ]

            if invalid_actions:
                allowed_acts = ", ".join(ALLOWED_RESOURCES[resource])
                return self._json_response(
                    error=f'Invalid actions for {resource}: {invalid_actions}. Allowed: [{allowed_acts}]',
                    status=400
                )

        operations_str = json.dumps(operations)

        rule = request.env['api.rules'].sudo().create({
            'name': name,
            'operations': operations_str,
        })
        return self._json_response(data={'id': rule.id, 'name': rule.name, 'operations': rule.operations}, status=201)

    @http.route(['/api/rules/<int:rule_id>'], type='http', auth='public', methods=['PUT', 'DELETE'], csrf=False)
    def api_rule_detail(self, rule_id, **kwargs):
        auth_user = self._authenticate()
        if not auth_user:
            return self._json_response(error='Unauthorized', status=401)
        if not self._has_model('api.rules'):
            return self._json_response(
                error='API rule model is not available. Upgrade the healthy_api module first.',
                status=503,
            )

        rule = request.env['api.rules'].sudo().browse(rule_id).exists()
        if not rule:
            return self._json_response(error='Rule not found', status=404)

        if request.httprequest.method == 'DELETE':
            rule.sudo().unlink()
            return self._json_response(data={'message': 'Rule deleted successfully'})

        # PUT: modify rule
        payload = self._parse_json_payload()
        if not payload:
            return self._json_response(error='Invalid JSON payload', status=400)

        vals = {}
        if 'name' in payload:
            vals['name'] = payload.get('name')
        if 'operations' in payload:
            operations = payload.get('operations')
            if isinstance(operations, (dict, list)):
                vals['operations'] = json.dumps(operations)
            else:
                vals['operations'] = operations or ''

        if vals:
            rule.sudo().write(vals)

        return self._json_response(data={'id': rule.id, 'name': rule.name, 'operations': rule.operations})

    @http.route(['/api/users/<int:user_id>/rules'], type='http', auth='public', methods=['PUT'], csrf=False)
    def assign_user_rules(self, user_id, **kwargs):
        auth_user = self._authenticate()
        if not auth_user:
            return self._json_response(error='Unauthorized', status=401)
        if not self._has_model('api.rules'):
            return self._json_response(
                error='API rule model is not available. Upgrade the healthy_api module first.',
                status=503,
            )

        # Allow Admin to assign rules
        if not self._is_admin(auth_user):
            return self._forbidden_response()

        user = self._get_user_by_id(user_id)
        if not user:
            return self._json_response(error='User not found', status=404)

        payload = self._parse_json_payload()
        if not payload:
            return self._json_response(error='Invalid JSON payload', status=400)

        rule_ids = payload.get('rule_ids')
        if not isinstance(rule_ids, list):
            return self._json_response(error='rule_ids must be a list', status=400)

        # Validate rules
        rules = request.env['api.rules'].sudo().browse(rule_ids).exists()
        if len(rules) != len(rule_ids):
            return self._json_response(error='One or more rule_ids are invalid', status=400)

        user.sudo().write({
            'api_rule_ids': [(6, 0, rules.ids)]
        })

        return self._json_response(data=self._serialize_user(user))
