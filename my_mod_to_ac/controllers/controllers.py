# -*- coding: utf-8 -*-
# from odoo import http


# class ActivateEnterpriseDb(http.Controller):
#     @http.route('/activate_enterprise_db/activate_enterprise_db', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/activate_enterprise_db/activate_enterprise_db/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('activate_enterprise_db.listing', {
#             'root': '/activate_enterprise_db/activate_enterprise_db',
#             'objects': http.request.env['activate_enterprise_db.activate_enterprise_db'].search([]),
#         })

#     @http.route('/activate_enterprise_db/activate_enterprise_db/objects/<model("activate_enterprise_db.activate_enterprise_db"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('activate_enterprise_db.object', {
#             'object': obj
#         })
