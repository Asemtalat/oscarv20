from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import date, timedelta


class HrEmployeeDocument(models.Model):
    _inherit = 'hr.employee.document'

    def mail_reminder(self):
        """Override to add activity notification after sending the reminder."""
        for record in self.search([('expiry_date', '!=', False)]):
            employee_name = record.employee_ref_id.name
            document_name = record.name
            expiry_date_str = str(record.expiry_date)
            exp_date = fields.Date.to_date(record.expiry_date)
            days_before = timedelta(days=record.before_days or 0)
            is_expiry_today = fields.Date.today() == exp_date
            msg = f"Hello {employee_name}, Document {document_name} is going to expire on {expiry_date_str}. Please renew it before the expiry date."
            is_notification_day = any([record.notification_type == 'single'
                                       and is_expiry_today,
                                       record.notification_type == 'multi'
                                       and (fields.Date.today() == fields.Date.to_date(record.expiry_date) - days_before
                                            or is_expiry_today),
                                       record.notification_type == 'everyday'
                                       and fields.Date.today() >= fields.Date.to_date(record.expiry_date) - days_before,
                                       record.notification_type ==
                                       'everyday_after'
                                       and fields.Date.today() <=
                                       fields.Date.to_date(record.expiry_date) + days_before,
                                       not record.notification_type and
                                       fields.Date.today() == fields.Date.to_date(record.expiry_date) - timedelta(
                                           days=7), ])
            if is_notification_day:
                users = self.get_group_employee_document_users()
                for user in users:
                    self.activity_notification(user, record.employee_ref_id, msg)


    def get_group_employee_document_users(self):
        """Fetches the users belonging to the 'Employee Document Notification' group.
               If the group is not found, returns all users."""

        group = self.env.ref('system_notification.group_employee_document_notification', raise_if_not_found=False)
        return group.user_ids if group else self.env['res.users']


    def activity_notification(self, user, empl, message):
        """Creates an activity notification for a specific user related to an employee document.
              If the document exists, an activity is created with a summary message and a deadline."""

        self = self.sudo()
        try:
            activity_type = self.env.ref("mail.mail_activity_data_todo")
        except ValueError:
            activity_type = False
        if not empl.exists():
            raise UserError(_("The document record does not exist or has been deleted."))
        if activity_type:
            try:
                res_model_id = self.env.ref('hr.model_hr_employee').id
                self.env['mail.activity'].create({
                    'activity_type_id': activity_type.id,
                    'summary': "Document Expiry Notification",
                    'note': message,
                    'user_id': user.id,
                    'res_id': empl.id,
                    'res_model': 'hr.employee',
                    'date_deadline': fields.Date.today(),
                    'res_model_id': res_model_id
                })
            except Exception as e:
                raise UserError(f"Error creating activity: {str(e)}")
