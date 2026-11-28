# -*- coding: utf-8 -*-
# from odoo import http


# class SystemNotification(http.Controller):
#     @http.route('/system_notification/system_notification', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/system_notification/system_notification/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('system_notification.listing', {
#             'root': '/system_notification/system_notification',
#             'objects': http.request.env['system_notification.system_notification'].search([]),
#         })

#     @http.route('/system_notification/system_notification/objects/<model("system_notification.system_notification"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('system_notification.object', {
#             'object': obj
#         })

