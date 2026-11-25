"""
HTTP controllers exposing REST endpoints for a mobile application.

Each endpoint requires a valid API token to be provided either through
the ``X-API-Key`` HTTP header or as a ``token`` parameter. The token is
stored on the user record (see :mod:`healthy_api.models.res_users`).

The endpoints cover read‑only retrieval of users, merchants, products,
inventory and offers, and the creation of sales orders, invoices and
credit notes. Responses are JSON objects with minimal metadata.
"""

import logging
from datetime import datetime
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class HealthyAPIController(http.Controller):
    """Public controller exposing the mobile API.

    All endpoints use ``auth='none'`` so that Odoo does not attempt to
    authenticate via the normal web session. Instead a token passed via
    header or parameter is validated against the users table. Once
    authenticated the request is executed with the privileges of that
    user (using :meth:`env.with_user`).
    """

    def _authenticate(self, token):
        """Return the user matching the provided API token.

        :param str token: the API token extracted from the request
        :returns: res.users record or False
        """
        if not token:
            return False
        user = request.env['res.users'].sudo().search([('api_token', '=', token)], limit=1)
        return user if user else False

    def _get_authenticated_env(self):
        """Retrieve the authenticated environment for the current request.

        This helper extracts the API token from either the ``X-API-Key``
        header or a query parameter named ``token``/``api_key``. It then
        searches the user table and, if found, returns an environment bound
        to that user. If no valid token is provided an exception is raised.

        :returns: ``(env, user)`` tuple where ``env`` is an Odoo Environment
        configured with the authenticated user
        :raises: http.Response if authentication fails
        """
        # Extract token from header or parameters
        token = request.httprequest.headers.get('X-API-Key') or \
            request.params.get('token') or request.params.get('api_key')
        # For JSON requests also check the JSON body
        if not token and hasattr(request, 'jsonrequest'):
            token = request.jsonrequest.get('token') if request.jsonrequest else None
        user = self._authenticate(token)
        if not user:
            # Return 401 Unauthorized
            return http.Response(
                status=401,
                headers={'WWW-Authenticate': 'Token'},
                content_type='application/json',
                response=b'{"error": "Unauthorized"}'
            )
        return request.env(user=user), user

    # ------------------------------------------------------------------
    # Users
    # ------------------------------------------------------------------
    @http.route('/api/users', type='json', auth='none', methods=['GET'], csrf=False)
    def api_get_users(self, **kwargs):
        """Return a list of users with basic information.

        Required fields per specification:
            - id
            - name
            - role (delivery / supervisor / admin)
            - active
            - assigned_merchants: list of partner IDs assigned to the user

        The role is derived from the group membership. If the user belongs to
        the technical settings group (System), they are considered ``admin``.
        Otherwise if they belong to the Administrator group they are
        ``supervisor``; all other users are considered ``delivery``.
        """
        env_user = self._get_authenticated_env()
        # If authentication failed, _get_authenticated_env returns Response
        if isinstance(env_user, http.Response):
            return env_user
        env, caller = env_user

        users = env['res.users'].search([])
        result = []
        for usr in users:
            # Determine role from groups
            role = 'delivery'
            try:
                if usr.has_group('base.group_system'):
                    role = 'admin'
                elif usr.has_group('base.group_erp_manager'):
                    role = 'supervisor'
            except Exception:
                pass
            # Assigned merchants: partners where this user is the salesperson
            merchant_ids = env['res.partner'].search([('user_id', '=', usr.id)]).ids
            result.append({
                'id': usr.id,
                'name': usr.name,
                'role': role,
                'active': usr.active,
                'assigned_merchants': merchant_ids,
            })
        return {'users': result}

    # ------------------------------------------------------------------
    # Merchants
    # ------------------------------------------------------------------
    @http.route('/api/merchants', type='json', auth='none', methods=['GET', 'POST'], csrf=False)
    def api_merchants(self, **kwargs):
        """Retrieve or create merchants (partners).

        GET parameters:
            - merchant_id: optional integer to fetch a single merchant
        POST JSON body:
            - name: required
            - phone: optional
            - street: optional
            - vat: optional VAT/tax number
            - latitude / longitude: optional floats
            - user_id: optional salesperson (delivery user) id

        Returns a single merchant or a list of all merchants marked as
        customers (``customer_rank > 0``).
        """
        env_user = self._get_authenticated_env()
        if isinstance(env_user, http.Response):
            return env_user
        env, caller = env_user

        if request.httprequest.method == 'POST':
            data = request.jsonrequest or {}
            name = data.get('name')
            if not name:
                return {'error': 'Name is required'}
            partner_vals = {
                'name': name,
                'phone': data.get('phone'),
                'street': data.get('street'),
                'vat': data.get('vat'),
                'customer_rank': 1,
            }
            # geo coordinates
            lat = data.get('latitude') or data.get('lat')
            lon = data.get('longitude') or data.get('lon')
            if lat:
                partner_vals['partner_latitude'] = lat
            if lon:
                partner_vals['partner_longitude'] = lon
            # assign delivery user as salesperson
            user_id = data.get('user_id') or data.get('delivery_user_id')
            if user_id:
                partner_vals['user_id'] = user_id
            partner = env['res.partner'].create(partner_vals)
            return {'merchant': {
                'id': partner.id,
                'name': partner.name,
                'phone': partner.phone,
                'address': partner.street,
                'vat': partner.vat,
                'latitude': getattr(partner, 'partner_latitude', None),
                'longitude': getattr(partner, 'partner_longitude', None),
                'user_id': partner.user_id.id,
            }}
        else:
            merchant_id = request.params.get('merchant_id') or kwargs.get('merchant_id')
            domain = [('customer_rank', '>', 0)]
            if merchant_id:
                domain.append(('id', '=', int(merchant_id)))
            partners = env['res.partner'].search(domain)
            result = []
            for partner in partners:
                result.append({
                    'id': partner.id,
                    'name': partner.name,
                    'phone': partner.phone,
                    'address': partner.street,
                    'vat': partner.vat,
                    'latitude': getattr(partner, 'partner_latitude', None),
                    'longitude': getattr(partner, 'partner_longitude', None),
                    'user_id': partner.user_id.id,
                })
            if merchant_id and result:
                return {'merchant': result[0]}
            return {'merchants': result}

    # ------------------------------------------------------------------
    # Products
    # ------------------------------------------------------------------
    @http.route('/api/products', type='json', auth='none', methods=['GET'], csrf=False)
    def api_products(self, **kwargs):
        """Return a list of saleable products.

        Each product record includes:
            - id
            - name
            - default_code (SKU)
            - barcode
            - list_price (sale price)
            - taxes (ids of customer taxes)
            - active
        """
        env_user = self._get_authenticated_env()
        if isinstance(env_user, http.Response):
            return env_user
        env, caller = env_user
        products = env['product.product'].search([('sale_ok', '=', True), ('active', '=', True)])
        result = []
        for prod in products:
            result.append({
                'id': prod.id,
                'name': prod.name,
                'default_code': prod.default_code,
                'barcode': prod.barcode,
                'list_price': prod.lst_price,
                'taxes': prod.taxes_id.ids,
                'active': prod.active,
            })
        return {'products': result}

    # ------------------------------------------------------------------
    # Inventory
    # ------------------------------------------------------------------
    @http.route('/api/inventory', type='json', auth='none', methods=['GET'], csrf=False)
    def api_inventory(self, **kwargs):
        """Return stock levels per product and location.

        Parameters:
            - product_id: optional to filter on a single product
            - location_id: optional to filter on a specific location

        Each entry in the returned list contains:
            - product_id: the product variant
            - product_name: product display name
            - location_id: the stock location
            - location_name: location display name
            - quantity: available quantity in this location
        """
        env_user = self._get_authenticated_env()
        if isinstance(env_user, http.Response):
            return env_user
        env, caller = env_user
        product_id = request.params.get('product_id') or kwargs.get('product_id')
        location_id = request.params.get('location_id') or kwargs.get('location_id')
        domain = []
        if product_id:
            domain.append(('product_id', '=', int(product_id)))
        if location_id:
            domain.append(('location_id', '=', int(location_id)))
        # Use sudo() to read quants regardless of access rights
        quants = env['stock.quant'].sudo().search(domain)
        result = []
        for quant in quants:
            result.append({
                'product_id': quant.product_id.id,
                'product_name': quant.product_id.display_name,
                'location_id': quant.location_id.id,
                'location_name': quant.location_id.display_name,
                'quantity': quant.quantity,
            })
        return {'inventory': result}

    # ------------------------------------------------------------------
    # Sales Orders
    # ------------------------------------------------------------------
    @http.route('/api/sale_orders', type='json', auth='none', methods=['GET', 'POST'], csrf=False)
    def api_sale_orders(self, **kwargs):
        """Retrieve or create sales orders.

        GET parameters:
            - order_id: optional integer to fetch a single order
            - merchant_id: optional integer to filter orders by partner
            - user_id: optional integer to filter by salesperson

        POST JSON body should include:
            - merchant_id: partner ID (required)
            - delivery_user_id: sales person / delivery user ID (optional)
            - lines: a list of {product_id, quantity} items (required)
            - date_order: ISO formatted date/time string (optional; defaults to now)
            - status: 'draft' (default) or 'confirm'

        When status is 'confirm' the order will be confirmed after creation.
        """
        env_user = self._get_authenticated_env()
        if isinstance(env_user, http.Response):
            return env_user
        env, caller = env_user
        SalesOrder = env['sale.order']

        if request.httprequest.method == 'POST':
            data = request.jsonrequest or {}
            merchant_id = data.get('merchant_id') or data.get('partner_id')
            lines = data.get('lines') or []
            if not merchant_id or not lines:
                return {'error': 'merchant_id and lines are required'}
            order_vals = {
                'partner_id': merchant_id,
            }
            if data.get('delivery_user_id'):
                order_vals['user_id'] = data['delivery_user_id']
            # parse order date if provided
            date_order_str = data.get('date_order')
            if date_order_str:
                try:
                    order_vals['date_order'] = datetime.fromisoformat(date_order_str)
                except Exception:
                    pass
            # prepare order lines
            order_line_vals = []
            for line in lines:
                product_id = line.get('product_id')
                qty = line.get('quantity', 1.0)
                if not product_id:
                    continue
                prod = env['product.product'].browse(product_id)
                price_unit = line.get('price_unit', prod.lst_price)
                order_line_vals.append((0, 0, {
                    'product_id': product_id,
                    'product_uom_qty': qty,
                    'price_unit': price_unit,
                }))
            order_vals['order_line'] = order_line_vals
            order = SalesOrder.create(order_vals)
            # confirm if requested
            if data.get('status', 'draft') == 'confirm':
                try:
                    order.action_confirm()
                except Exception as e:
                    _logger.exception("Failed to confirm sale order: %s", e)
            return {'sale_order': {
                'id': order.id,
                'name': order.name,
                'state': order.state,
            }}
        else:
            order_id = request.params.get('order_id') or kwargs.get('order_id')
            domain = []
            if order_id:
                domain.append(('id', '=', int(order_id)))
            if request.params.get('merchant_id'):
                domain.append(('partner_id', '=', int(request.params.get('merchant_id'))))
            if request.params.get('user_id'):
                domain.append(('user_id', '=', int(request.params.get('user_id'))))
            orders = SalesOrder.search(domain)
            result = []
            for order in orders:
                lines = []
                for line in order.order_line:
                    lines.append({
                        'product_id': line.product_id.id,
                        'product_name': line.product_id.display_name,
                        'quantity': line.product_uom_qty,
                        'price_unit': line.price_unit,
                        'subtotal': line.price_subtotal,
                    })
                result.append({
                    'id': order.id,
                    'name': order.name,
                    'partner_id': order.partner_id.id,
                    'partner_name': order.partner_id.display_name,
                    'user_id': order.user_id.id,
                    'date_order': order.date_order.isoformat() if order.date_order else None,
                    'state': order.state,
                    'lines': lines,
                })
            if order_id and result:
                return {'sale_order': result[0]}
            return {'sale_orders': result}

    # ------------------------------------------------------------------
    # Invoices
    # ------------------------------------------------------------------
    @http.route('/api/invoices', type='json', auth='none', methods=['GET', 'POST'], csrf=False)
    def api_invoices(self, **kwargs):
        """Retrieve or create customer invoices.

        POST JSON body should include:
            - merchant_id: customer/partner ID (required)
            - user_id: salesperson/delivery user ID (optional)
            - lines: list of {product_id, quantity, price_unit, discount (optional)}
            - invoice_date: ISO formatted date/time string (optional; defaults to today)
            - payment_method: description (string) (ignored by this simple implementation)

        The invoice is posted immediately after creation. The response includes
        the invoice id, name and state.
        """
        env_user = self._get_authenticated_env()
        if isinstance(env_user, http.Response):
            return env_user
        env, caller = env_user
        Invoice = env['account.move']

        if request.httprequest.method == 'POST':
            data = request.jsonrequest or {}
            partner_id = data.get('merchant_id') or data.get('partner_id')
            lines = data.get('lines') or []
            if not partner_id or not lines:
                return {'error': 'merchant_id and lines are required'}
            move_vals = {
                'move_type': 'out_invoice',
                'partner_id': partner_id,
            }
            if data.get('invoice_date'):
                try:
                    move_vals['invoice_date'] = datetime.fromisoformat(data['invoice_date']).date()
                except Exception:
                    pass
            if data.get('user_id'):
                move_vals['invoice_user_id'] = data['user_id']
            invoice_lines = []
            for line in lines:
                product_id = line.get('product_id')
                qty = line.get('quantity', 1.0)
                if not product_id:
                    continue
                prod = env['product.product'].browse(product_id)
                price_unit = line.get('price_unit', prod.lst_price)
                discount = line.get('discount', 0.0)
                invoice_lines.append((0, 0, {
                    'product_id': product_id,
                    'quantity': qty,
                    'price_unit': price_unit,
                    'discount': discount,
                    # set tax ids based on the product's taxes
                    'tax_ids': [(6, 0, prod.taxes_id.ids)],
                }))
            move_vals['invoice_line_ids'] = invoice_lines
            move = Invoice.create(move_vals)
            try:
                move.action_post()
            except Exception as e:
                _logger.exception("Failed to post invoice: %s", e)
            return {'invoice': {
                'id': move.id,
                'name': move.name,
                'state': move.state,
            }}
        else:
            invoice_id = request.params.get('invoice_id') or kwargs.get('invoice_id')
            domain = [('move_type', '=', 'out_invoice')]
            if invoice_id:
                domain.append(('id', '=', int(invoice_id)))
            invoices = Invoice.search(domain)
            result = []
            for inv in invoices:
                lines = []
                for line in inv.invoice_line_ids:
                    lines.append({
                        'product_id': line.product_id.id,
                        'product_name': line.product_id.display_name,
                        'quantity': line.quantity,
                        'price_unit': line.price_unit,
                        'discount': line.discount,
                        'subtotal': line.price_subtotal,
                    })
                result.append({
                    'id': inv.id,
                    'name': inv.name,
                    'partner_id': inv.partner_id.id,
                    'partner_name': inv.partner_id.display_name,
                    'invoice_date': inv.invoice_date.isoformat() if inv.invoice_date else None,
                    'state': inv.state,
                    'amount_total': inv.amount_total,
                    'lines': lines,
                })
            if invoice_id and result:
                return {'invoice': result[0]}
            return {'invoices': result}

    # ------------------------------------------------------------------
    # Credit Notes (Returns)
    # ------------------------------------------------------------------
    @http.route('/api/returns', type='json', auth='none', methods=['POST'], csrf=False)
    def api_returns(self, **kwargs):
        """Create a credit note (return) against an existing invoice.

        POST JSON body must include:
            - original_invoice_id: ID of the invoice being returned (required)
            - lines: list of {product_id, quantity, price_unit (optional)} (required)
            - reason: text describing why the return is occurring (optional)
            - return_date: ISO formatted date string (optional; defaults to today)

        Returns the created credit note with its id, name and state.
        """
        env_user = self._get_authenticated_env()
        if isinstance(env_user, http.Response):
            return env_user
        env, caller = env_user
        data = request.jsonrequest or {}
        orig_id = data.get('original_invoice_id') or data.get('invoice_id')
        lines = data.get('lines') or []
        if not orig_id or not lines:
            return {'error': 'original_invoice_id and lines are required'}
        original = env['account.move'].browse(int(orig_id))
        if not original or original.move_type != 'out_invoice':
            return {'error': 'Invalid original invoice'}
        move_vals = {
            'move_type': 'out_refund',
            'partner_id': original.partner_id.id,
            'invoice_origin': original.name,
            'ref': data.get('reason'),
        }
        if data.get('return_date'):
            try:
                move_vals['invoice_date'] = datetime.fromisoformat(data['return_date']).date()
            except Exception:
                pass
        invoice_lines = []
        for line in lines:
            prod_id = line.get('product_id')
            qty = line.get('quantity', 1.0)
            if not prod_id:
                continue
            prod = env['product.product'].browse(prod_id)
            price_unit = line.get('price_unit', prod.lst_price)
            invoice_lines.append((0, 0, {
                'product_id': prod_id,
                'quantity': qty,
                'price_unit': price_unit,
                'tax_ids': [(6, 0, prod.taxes_id.ids)],
            }))
        move_vals['invoice_line_ids'] = invoice_lines
        move = env['account.move'].create(move_vals)
        try:
            move.action_post()
        except Exception as e:
            _logger.exception("Failed to post credit note: %s", e)
        return {'return': {
            'id': move.id,
            'name': move.name,
            'state': move.state,
        }}

    # ------------------------------------------------------------------
    # Offers & Promotions
    # ------------------------------------------------------------------
    @http.route('/api/offers', type='json', auth='none', methods=['GET'], csrf=False)
    def api_offers(self, **kwargs):
        """Return a list of price lists (offers/promotions).

        Each record includes the price list id, name, currency and validity range
        (date_start/date_end). This simple implementation returns all price
        lists regardless of assignment or activation.
        """
        env_user = self._get_authenticated_env()
        if isinstance(env_user, http.Response):
            return env_user
        env, caller = env_user
        pricelists = env['product.pricelist'].search([])
        result = []
        for pl in pricelists:
            result.append({
                'id': pl.id,
                'name': pl.name,
                'currency_id': pl.currency_id.id,
                'currency': pl.currency_id.name,
                'date_start': pl.active_date_from.isoformat() if getattr(pl, 'active_date_from', False) else None,
                'date_end': pl.active_date_to.isoformat() if getattr(pl, 'active_date_to', False) else None,
            })
        return {'offers': result}