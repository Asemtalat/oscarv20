from odoo import api, fields, models


class ResourceCalendarShiftLine(models.Model):
    _name = 'resource.calendar.shift.line'
    _description = 'Resource Calendar Shift Rotation Line'
    _order = 'calendar_id, shift_rotation_week, date_from, id'

    name = fields.Char(required=True, default='Shift Rotation')
    calendar_id = fields.Many2one('resource.calendar', required=True, ondelete='cascade', index=True)
    is_shift_rotation_line = fields.Boolean(default=True, readonly=True)
    auto_generated = fields.Boolean(
        default=False,
        copy=False,
        help='Technical flag for lines generated automatically from shift rotation week ranges.',
    )
    shift_rotation_week = fields.Selection(
        selection=[
            ('1', 'Week 1'),
            ('2', 'Week 2'),
            ('3', 'Week 3'),
            ('4', 'Week 4'),
        ],
        required=True,
        index=True,
    )
    date_from = fields.Date(required=True, index=True)
    date_to = fields.Date(required=True, index=True)
    dayofweek = fields.Selection(
        selection=[
            ('0', 'Monday'),
            ('1', 'Tuesday'),
            ('2', 'Wednesday'),
            ('3', 'Thursday'),
            ('4', 'Friday'),
            ('5', 'Saturday'),
            ('6', 'Sunday'),
        ],
        required=True,
    )
    day_period = fields.Selection(
        selection=[
            ('morning', 'Morning'),
            ('afternoon', 'Afternoon'),
            ('lunch', 'Break'),
        ],
        default='morning',
        required=True,
    )
    hour_from = fields.Float(required=True, digits=(16, 2))
    hour_to = fields.Float(required=True, digits=(16, 2))
    duration_hours = fields.Float(compute='_compute_duration_hours', string='Duration (hours)')
    duration_days = fields.Float(compute='_compute_duration_days', string='Duration (days)', store=True, readonly=False)

    def _hour_span(self):
        self.ensure_one()
        return max((self.hour_to or 0.0) - (self.hour_from or 0.0), 0.0)

    @api.depends('hour_from', 'hour_to', 'day_period')
    def _compute_duration_hours(self):
        for line in self:
            line.duration_hours = line._hour_span() if line.day_period != 'lunch' else 0.0

    @api.depends('day_period', 'duration_hours', 'calendar_id.hours_per_day')
    def _compute_duration_days(self):
        for line in self:
            if line.day_period == 'lunch' or not line.duration_hours:
                line.duration_days = 0.0
            elif line.calendar_id.hours_per_day:
                line.duration_days = 0.5 if line.duration_hours <= line.calendar_id.hours_per_day * 3 / 4 else 1.0
            else:
                line.duration_days = 0.0
