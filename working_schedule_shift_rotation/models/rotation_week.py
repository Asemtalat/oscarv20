from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ResourceCalendarRotationWeek(models.Model):
    _name = 'resource.calendar.rotation.week'
    _description = 'Working Schedule Rotation Week'
    _order = 'calendar_id, week_number'

    calendar_id = fields.Many2one(
        'resource.calendar',
        required=True,
        ondelete='cascade',
    )
    week_number = fields.Selection(
        selection=[
            ('1', 'Week 1'),
            ('2', 'Week 2'),
            ('3', 'Week 3'),
            ('4', 'Week 4'),
        ],
        required=True,
        default='1',
    )
    date_from = fields.Date(string='From')
    date_to = fields.Date(string='To')
    period = fields.Selection(
        selection=[
            ('morning', 'Morning'),
            ('afternoon', 'Afternoon'),
            ('full_day', 'Full Day'),
        ],
        string='Period',
        default='full_day',
        required=True,
    )

    _rotation_week_unique = models.Constraint(
        'unique(calendar_id, week_number)',
        "Each week can only be configured once per schedule.",
    )

    @api.constrains('date_from', 'date_to')
    def _check_date_range(self):
        for record in self:
            if record.date_from and record.date_to and record.date_to < record.date_from:
                raise ValidationError(_('Week end date must be greater than or equal to start date.'))
            if bool(record.date_from) != bool(record.date_to):
                raise ValidationError(_('Please set both week start and end dates.'))

    # This model is kept for backward compatibility only.
