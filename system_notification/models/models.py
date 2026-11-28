from odoo import models, fields, _


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def button_validate(self):
        res = super().button_validate()
        for picking in self:
            if picking.purchase_id:
                product_names = ', '.join(picking.move_ids.mapped('product_id.name'))
                msg = _("Products for purchase order %s have been received: %s") % (picking.purchase_id.name,
                                                                                    product_names)
                users = self.get_notification_users()
                for user in users:
                    picking.send_notification(msg, user)
        return res

    def get_notification_users(self):
        group = self.env.ref('system_notification.group_notification_user', raise_if_not_found=False)
        return group.user_ids if group else self.env['res.users']

    def send_notification(self, message, user):
        # Odoo 20: channel_get() was replaced by _get_or_create_chat(), which returns the channel record
        channel = self.env['discuss.channel']._get_or_create_chat(partners_to=[user.partner_id.id])
        channel.message_post(
            body=message,
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
        )
        return True
