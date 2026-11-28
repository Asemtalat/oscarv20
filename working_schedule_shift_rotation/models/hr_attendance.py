from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    @api.constrains('employee_id', 'check_in', 'check_out')
    def _check_shift_rotation_configuration(self):
        for attendance in self:
            if not attendance.employee_id or not attendance.check_in:
                continue

            calendar = attendance.employee_id.resource_calendar_id or attendance.employee_id.company_id.resource_calendar_id
            if not calendar or not calendar.shift_rotation:
                continue

            start_date = fields.Datetime.to_datetime(attendance.check_in).date()
            stop_dt = fields.Datetime.to_datetime(attendance.check_out) if attendance.check_out else fields.Datetime.to_datetime(attendance.check_in)
            end_date = stop_dt.date()

            rotation_lines = calendar._get_shift_rotation_lines_in_range(start_date, end_date)
            if not rotation_lines:
                raise ValidationError(_(
                    'No shift rotation lines were generated for this attendance date. '
                    'Please set Week 1..4 date ranges on the working schedule.'
                ))
            if not rotation_lines.filtered(lambda line: line.hour_to > line.hour_from):
                raise ValidationError(_(
                    'Shift rotation lines exist but hours are not configured. '
                    'Please set start/end hours on Working Hours lines before creating attendance.'
                ))
