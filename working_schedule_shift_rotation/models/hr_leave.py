from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class HrLeave(models.Model):
    _inherit = 'hr.leave'

    @api.constrains('employee_id', 'date_from', 'date_to', 'state')
    def _check_shift_rotation_configuration(self):
        for leave in self:
            if leave.state in ('cancel', 'refuse'):
                continue
            if not leave.employee_id or not leave.date_from or not leave.date_to:
                continue

            calendar = leave.employee_id.resource_calendar_id or leave.employee_id.company_id.resource_calendar_id
            if not calendar or not calendar.shift_rotation:
                continue

            start_date = fields.Datetime.to_datetime(leave.date_from).date()
            end_date = fields.Datetime.to_datetime(leave.date_to).date()
            rotation_lines = calendar._get_shift_rotation_lines_in_range(start_date, end_date)
            if not rotation_lines:
                raise ValidationError(_(
                    'No shift rotation lines were generated for this time off range. '
                    'Please set Week 1..4 date ranges on the working schedule.'
                ))
            if not rotation_lines.filtered(lambda line: line.hour_to > line.hour_from):
                raise ValidationError(_(
                    'Shift rotation lines exist but hours are not configured. '
                    'Please set start/end hours on Working Hours lines before creating time off.'
                ))
