from datetime import UTC, datetime, timedelta

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.fields import Domain
from odoo.tools.date_utils import float_to_time
from odoo.tools.intervals import Intervals

WEEK_SELECTION = [
    ('1', 'Week 1'),
    ('2', 'Week 2'),
    ('3', 'Week 3'),
    ('4', 'Week 4'),
]


class ResourceCalendar(models.Model):
    _inherit = 'resource.calendar'

    shift_rotation = fields.Boolean(string='Shift Rotation')
    rotation_week_1_from = fields.Date(string='Week 1 From')
    rotation_week_1_to = fields.Date(string='Week 1 To')
    rotation_week_1_period = fields.Selection(
        WEEK_SELECTION,
        string='Week 1 Period',
        default='1',
    )
    rotation_week_2_from = fields.Date(string='Week 2 From')
    rotation_week_2_to = fields.Date(string='Week 2 To')
    rotation_week_2_period = fields.Selection(
        WEEK_SELECTION,
        string='Week 2 Period',
        default='2',
    )
    rotation_week_3_from = fields.Date(string='Week 3 From')
    rotation_week_3_to = fields.Date(string='Week 3 To')
    rotation_week_3_period = fields.Selection(
        WEEK_SELECTION,
        string='Week 3 Period',
        default='3',
    )
    rotation_week_4_from = fields.Date(string='Week 4 From')
    rotation_week_4_to = fields.Date(string='Week 4 To')
    rotation_week_4_period = fields.Selection(
        WEEK_SELECTION,
        string='Week 4 Period',
        default='4',
    )
    rotation_week_1_attendance_line_ids = fields.One2many(
        'resource.calendar.shift.line',
        'calendar_id',
        domain=[('shift_rotation_week', '=', '1')],
        string='Week 1 Attendance Lines',
    )
    rotation_week_2_attendance_line_ids = fields.One2many(
        'resource.calendar.shift.line',
        'calendar_id',
        domain=[('shift_rotation_week', '=', '2')],
        string='Week 2 Attendance Lines',
    )
    rotation_week_3_attendance_line_ids = fields.One2many(
        'resource.calendar.shift.line',
        'calendar_id',
        domain=[('shift_rotation_week', '=', '3')],
        string='Week 3 Attendance Lines',
    )
    rotation_week_4_attendance_line_ids = fields.One2many(
        'resource.calendar.shift.line',
        'calendar_id',
        domain=[('shift_rotation_week', '=', '4')],
        string='Week 4 Attendance Lines',
    )

    # Default hours, applied to all lines in the week when changed
    rotation_week_1_default_hour_from = fields.Float(string='Work From', digits=(16, 2))
    rotation_week_1_default_hour_to = fields.Float(string='Work To', digits=(16, 2))
    rotation_week_2_default_hour_from = fields.Float(string='Work From', digits=(16, 2))
    rotation_week_2_default_hour_to = fields.Float(string='Work To', digits=(16, 2))
    rotation_week_3_default_hour_from = fields.Float(string='Work From', digits=(16, 2))
    rotation_week_3_default_hour_to = fields.Float(string='Work To', digits=(16, 2))
    rotation_week_4_default_hour_from = fields.Float(string='Work From', digits=(16, 2))
    rotation_week_4_default_hour_to = fields.Float(string='Work To', digits=(16, 2))

    # Total hours per week (computed from attendance lines)
    rotation_week_1_total_hours = fields.Float(
        string='Total Hours Week 1',
        compute='_compute_week_1_total_hours',
        store=True,
        digits=(16, 2),
    )
    rotation_week_2_total_hours = fields.Float(
        string='Total Hours Week 2',
        compute='_compute_week_2_total_hours',
        store=True,
        digits=(16, 2),
    )
    rotation_week_3_total_hours = fields.Float(
        string='Total Hours Week 3',
        compute='_compute_week_3_total_hours',
        store=True,
        digits=(16, 2),
    )
    rotation_week_4_total_hours = fields.Float(
        string='Total Hours Week 4',
        compute='_compute_week_4_total_hours',
        store=True,
        digits=(16, 2),
    )

    # ─────────────────────────────────────────────────────────────────────────
    # Constraints
    # ─────────────────────────────────────────────────────────────────────────

    @api.constrains(
        'rotation_week_1_from', 'rotation_week_1_to',
        'rotation_week_2_from', 'rotation_week_2_to',
        'rotation_week_3_from', 'rotation_week_3_to',
        'rotation_week_4_from', 'rotation_week_4_to',
    )
    def _check_rotation_date_ranges(self):
        for calendar in self:
            for idx in (1, 2, 3, 4):
                date_from = calendar[f'rotation_week_{idx}_from']
                date_to = calendar[f'rotation_week_{idx}_to']
                if bool(date_from) != bool(date_to):
                    raise ValidationError(f'Week {idx}: set both From and To dates.')
                if date_from and date_to and date_to < date_from:
                    raise ValidationError(f'Week {idx}: To date must be greater than or equal to From date.')

    @api.constrains(
        'shift_rotation',
        'rotation_week_1_from', 'rotation_week_1_to',
        'rotation_week_2_from', 'rotation_week_2_to',
        'rotation_week_3_from', 'rotation_week_3_to',
        'rotation_week_4_from', 'rotation_week_4_to',
    )
    def _check_all_weeks_configured(self):
        """
        When shift rotation is enabled, ALL 4 weeks must have at least
        one day configured (both From and To dates must be set).
        """
        for record in self:
            if not record.shift_rotation:
                continue
            missing_weeks = [
                f'Week {i}'
                for i in (1, 2, 3, 4)
                if not (record[f'rotation_week_{i}_from'] and record[f'rotation_week_{i}_to'])
            ]
            if missing_weeks:
                raise ValidationError(
                    'Shift Rotation requires all 4 weeks to have date ranges configured.\n'
                    f'Missing: {", ".join(missing_weeks)}'
                )

    # ─────────────────────────────────────────────────────────────────────────
    # Compute Methods — Total Hours per Week
    # ─────────────────────────────────────────────────────────────────────────


    @api.depends(
        'shift_rotation',
        'rotation_week_1_attendance_line_ids.hour_from',
        'rotation_week_1_attendance_line_ids.hour_to',
        'rotation_week_1_attendance_line_ids.day_period',
    )
    def _compute_hours_per_week(self):
        """Shift rotation calendars use Week 1 only, so that the work time
        rate is 100% (not 400% for a 4-week rotation). Other calendars keep
        Odoo's default behaviour (work_time_rate / is_fulltime are derived
        from hours_per_week by Odoo itself)."""
        rotation = self.filtered('shift_rotation')
        for calendar in rotation:
            calendar.hours_per_week = sum(
                line.hour_to - line.hour_from
                for line in calendar.rotation_week_1_attendance_line_ids
                if line.is_shift_rotation_line and line.day_period != 'lunch'
            )
        super(ResourceCalendar, self - rotation)._compute_hours_per_week()

    @api.depends(
        'shift_rotation',
        'rotation_week_1_attendance_line_ids.dayofweek',
        'rotation_week_1_attendance_line_ids.hour_from',
        'rotation_week_1_attendance_line_ids.hour_to',
        'rotation_week_1_attendance_line_ids.day_period',
    )
    def _compute_days_per_week(self):
        rotation = self.filtered('shift_rotation')
        for calendar in rotation:
            calendar.days_per_week = len(set(
                calendar.rotation_week_1_attendance_line_ids.filtered(
                    lambda l: l.day_period != 'lunch' and l.hour_to > l.hour_from
                ).mapped('dayofweek')
            ))
        super(ResourceCalendar, self - rotation)._compute_days_per_week()

    def _attendance_intervals_batch(self, start_dt, end_dt, resources_per_tz=None, domain=None):
        if not self or not self.shift_rotation:
            return super()._attendance_intervals_batch(
                start_dt, end_dt, resources_per_tz=resources_per_tz, domain=domain)

        assert start_dt.tzinfo and end_dt.tzinfo
        self.ensure_one()
        ShiftLine = self.env['resource.calendar.shift.line']
        Resource = self.env['resource.resource']
        if not resources_per_tz:
            resources_per_tz = {start_dt.tzinfo: Resource}

        shift_line_domain = Domain([
            ('calendar_id', '=', self.id),
            ('day_period', '!=', 'lunch'),
            ('date_from', '<=', end_dt.date()),
            ('date_to', '>=', start_dt.date()),
        ])
        if domain:
            # only keep the conditions that make sense on shift lines
            extra = Domain(domain).map_conditions(
                lambda cond: cond if cond.field_expr.split('.')[0] in ShiftLine._fields else Domain.TRUE
            )
            shift_line_domain = shift_line_domain & extra

        shift_lines = ShiftLine.search(shift_line_domain)
        result_per_resource_id = {}
        utc_start = start_dt.astimezone(UTC)
        utc_end = end_dt.astimezone(UTC)

        for tz_obj, tz_resources in resources_per_tz.items():
            local_start = start_dt.astimezone(tz_obj)
            local_end = end_dt.astimezone(tz_obj)
            intervals = []
            for line in shift_lines:
                current_day = max(line.date_from, local_start.date())
                last_day = min(line.date_to, local_end.date())
                while current_day <= last_day:
                    localized_start = datetime.combine(current_day, float_to_time(line.hour_from)).replace(tzinfo=tz_obj)
                    localized_stop = datetime.combine(current_day, float_to_time(line.hour_to)).replace(tzinfo=tz_obj)
                    if localized_stop > local_start and localized_start < local_end:
                        intervals.append((max(local_start, localized_start), min(local_end, localized_stop), line))
                    current_day += timedelta(days=1)

            tz_intervals = Intervals(intervals, keep_distinct=True)
            # same contract as the standard method: every resource plus the
            # calendar-level entry (key False)
            for resource in list(tz_resources) + [Resource]:
                if resource and resource._is_fully_flexible():
                    hours = (utc_end - utc_start).total_seconds() / 3600.0
                    dummy_line = ShiftLine.new({
                        'name': 'Shift Rotation',
                        'calendar_id': self.id,
                        'shift_rotation_week': '1',
                        'date_from': local_start.date(),
                        'date_to': local_end.date(),
                        'dayofweek': str(local_start.weekday()),
                        'day_period': 'morning',
                        'hour_from': 0.0,
                        'hour_to': 0.0,
                        'duration_hours': hours,
                        'duration_days': hours / 24.0,
                    })
                    result_per_resource_id[resource.id] = Intervals(
                        [(local_start, local_end, dummy_line)], keep_distinct=True)
                else:
                    result_per_resource_id[resource.id] = tz_intervals

        return result_per_resource_id

    @api.depends('rotation_week_1_attendance_line_ids.hour_from', 'rotation_week_1_attendance_line_ids.hour_to')
    def _compute_week_1_total_hours(self):
        for record in self:
            total = sum(
                line.hour_to - line.hour_from
                for line in record.rotation_week_1_attendance_line_ids
                if line.is_shift_rotation_line
            )
            record.rotation_week_1_total_hours = total

    @api.depends('rotation_week_2_attendance_line_ids.hour_from', 'rotation_week_2_attendance_line_ids.hour_to')
    def _compute_week_2_total_hours(self):
        for record in self:
            total = sum(
                line.hour_to - line.hour_from
                for line in record.rotation_week_2_attendance_line_ids
                if line.is_shift_rotation_line
            )
            record.rotation_week_2_total_hours = total

    @api.depends('rotation_week_3_attendance_line_ids.hour_from', 'rotation_week_3_attendance_line_ids.hour_to')
    def _compute_week_3_total_hours(self):
        for record in self:
            total = sum(
                line.hour_to - line.hour_from
                for line in record.rotation_week_3_attendance_line_ids
                if line.is_shift_rotation_line
            )
            record.rotation_week_3_total_hours = total

    @api.depends('rotation_week_4_attendance_line_ids.hour_from', 'rotation_week_4_attendance_line_ids.hour_to')
    def _compute_week_4_total_hours(self):
        for record in self:
            total = sum(
                line.hour_to - line.hour_from
                for line in record.rotation_week_4_attendance_line_ids
                if line.is_shift_rotation_line
            )
            record.rotation_week_4_total_hours = total

    # ─────────────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────────────

    @api.model
    def _normalize_date_value(self, value):
        return fields.Date.to_date(value) if value else False

    @api.model
    def _get_default_rotation_week_1_from(self):
        """First day of current month."""
        return fields.Date.context_today(self).replace(day=1)

    @api.model
    def _get_month_end(self, date_value):
        """Return last day of the month for the given date."""
        return ((date_value.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1))

    @api.model
    def _build_month_rotation_ranges(self, start_date):
        """Build 4 week ranges from start_date.

        Each week spans 7 working days, excluding Friday from the count.
        """
        ranges = []
        current_from = start_date
        for _week_idx in (1, 2, 3, 4):
            counted_days = 0
            current_to = current_from - timedelta(days=1)
            while counted_days < 7:
                current_to += timedelta(days=1)
                if current_to.weekday() == 4:  # Friday holiday
                    continue
                counted_days += 1
            ranges.append((current_from, current_to))
            current_from = current_to + timedelta(days=1)
        return ranges

    @api.model
    def _get_rotation_autofill_vals(self, values):
        if not values.get('shift_rotation'):
            return {}

        normalized = {
            f'rotation_week_{i}_{bound}': self._normalize_date_value(values.get(f'rotation_week_{i}_{bound}'))
            for i in (1, 2, 3, 4)
            for bound in ('from', 'to')
        }
        weeks_complete = all(
            normalized[f'rotation_week_{i}_from'] and normalized[f'rotation_week_{i}_to']
            for i in (1, 2, 3, 4)
        )
        if weeks_complete:
            return {}

        week_1_from = normalized['rotation_week_1_from'] or self._get_default_rotation_week_1_from()
        ranges = self._build_month_rotation_ranges(week_1_from)
        autofill = {}
        for idx, (date_from, date_to) in enumerate(ranges, start=1):
            current_from = normalized[f'rotation_week_{idx}_from']
            current_to = normalized[f'rotation_week_{idx}_to']
            if current_from and current_to:
                continue
            autofill[f'rotation_week_{idx}_from'] = date_from
            autofill[f'rotation_week_{idx}_to'] = date_to
        return autofill

    @api.model_create_multi
    def create(self, vals_list):
        prepared_vals_list = []
        for vals in vals_list:
            candidate = dict(vals)
            candidate.update(self._get_rotation_autofill_vals(candidate))
            if candidate.get('shift_rotation'):
                candidate.pop('attendance_ids', None)
            prepared_vals_list.append(candidate)
        records = super().create(prepared_vals_list)
        records._sync_rotation_lines()
        return records

    def write(self, vals):
        if not self:
            return True
        tracked_fields = {'shift_rotation'} | {
            f'rotation_week_{i}_{bound}'
            for i in (1, 2, 3, 4) for bound in ('from', 'to')
        }
        if not (tracked_fields & set(vals.keys())):
            return super().write(vals)

        toggle_only = set(vals.keys()) == {'shift_rotation'}
        for record in self:
            candidate = {
                'shift_rotation': vals.get('shift_rotation', record.shift_rotation),
            }
            for i in (1, 2, 3, 4):
                for bound in ('from', 'to'):
                    key = f'rotation_week_{i}_{bound}'
                    candidate[key] = vals.get(key, record[key])
            write_vals = dict(vals)
            write_vals.update(self._get_rotation_autofill_vals(candidate))
            if candidate.get('shift_rotation'):
                write_vals.pop('attendance_ids', None)
            super(ResourceCalendar, record).write(write_vals)
            # Shift lines are isolated from attendance_ids, so it's safe to auto-generate on toggle.
            if not toggle_only or candidate.get('shift_rotation'):
                record._sync_rotation_lines()
        return True

    @api.onchange('shift_rotation')
    def _onchange_shift_rotation_set_week_1_from(self):
        for calendar in self:
            if not calendar.shift_rotation:
                continue
            values = {'shift_rotation': calendar.shift_rotation}
            for i in (1, 2, 3, 4):
                values[f'rotation_week_{i}_from'] = calendar[f'rotation_week_{i}_from']
                values[f'rotation_week_{i}_to'] = calendar[f'rotation_week_{i}_to']
            autofill = calendar._get_rotation_autofill_vals(values)
            for key, value in autofill.items():
                calendar[key] = value

            if not calendar._rotation_weeks_complete():
                continue
            generated_vals = calendar._prepare_shift_rotation_line_vals()
            calendar.rotation_week_1_attendance_line_ids = [(5, 0, 0)] + [(0, 0, v) for v in generated_vals['1']]
            calendar.rotation_week_2_attendance_line_ids = [(5, 0, 0)] + [(0, 0, v) for v in generated_vals['2']]
            calendar.rotation_week_3_attendance_line_ids = [(5, 0, 0)] + [(0, 0, v) for v in generated_vals['3']]
            calendar.rotation_week_4_attendance_line_ids = [(5, 0, 0)] + [(0, 0, v) for v in generated_vals['4']]

    def _get_rotation_week_data(self):
        self.ensure_one()
        return [
            (1, self.rotation_week_1_from, self.rotation_week_1_to, self.rotation_week_1_period),
            (2, self.rotation_week_2_from, self.rotation_week_2_to, self.rotation_week_2_period),
            (3, self.rotation_week_3_from, self.rotation_week_3_to, self.rotation_week_3_period),
            (4, self.rotation_week_4_from, self.rotation_week_4_to, self.rotation_week_4_period),
        ]

    def _rotation_weeks_complete(self):
        self.ensure_one()
        return all(
            self[f'rotation_week_{i}_from'] and self[f'rotation_week_{i}_to']
            for i in (1, 2, 3, 4)
        )

    def _sync_rotation_lines(self):
        ShiftLine = self.env['resource.calendar.shift.line']
        for calendar in self:
            if not calendar.shift_rotation or not calendar._rotation_weeks_complete():
                continue

            generated_vals = calendar._prepare_shift_rotation_line_vals()
            new_vals = []
            for week in ('1', '2', '3', '4'):
                for vals in generated_vals[week]:
                    vals_with_calendar = dict(vals)
                    vals_with_calendar['calendar_id'] = calendar.id
                    new_vals.append(vals_with_calendar)

            (
                calendar.rotation_week_1_attendance_line_ids.filtered('auto_generated')
                | calendar.rotation_week_2_attendance_line_ids.filtered('auto_generated')
                | calendar.rotation_week_3_attendance_line_ids.filtered('auto_generated')
                | calendar.rotation_week_4_attendance_line_ids.filtered('auto_generated')
            ).unlink()
            if new_vals:
                ShiftLine.create(new_vals)

    def _shift_line_to_vals(self, line):
        return {
            'name': line.name or 'Shift Rotation',
            'is_shift_rotation_line': True,
            'auto_generated': bool(line.auto_generated),
            'shift_rotation_week': line.shift_rotation_week,
            'date_from': line.date_from,
            'date_to': line.date_to,
            'dayofweek': line.dayofweek,
            'day_period': line.day_period,
            'hour_from': line.hour_from,
            'hour_to': line.hour_to,
        }

    def _build_week_onchange_commands(self, week_bucket, generated_vals):
        self.ensure_one()
        field_name = f'rotation_week_{week_bucket}_attendance_line_ids'
        manual_lines = self[field_name].filtered(lambda line: not line.auto_generated)
        commands = [(5, 0, 0)]
        commands += [(0, 0, vals) for vals in generated_vals]
        commands += [(0, 0, self._shift_line_to_vals(line)) for line in manual_lines]
        return commands

    def _prepare_shift_rotation_line_vals(self):
        """Build one generated line per day in every configured week range,
        preserving any hours that were already entered by the user.
        Falls back to the week-level default Work From/To if no per-line hours exist."""
        self.ensure_one()
        # Snapshot existing hours so they survive regeneration
        existing_hours = {}
        manual_line_dates = set()
        existing_lines = (
            self.rotation_week_1_attendance_line_ids
            | self.rotation_week_2_attendance_line_ids
            | self.rotation_week_3_attendance_line_ids
            | self.rotation_week_4_attendance_line_ids
        )
        for line in existing_lines:
            key = (line.shift_rotation_week, line.date_from)
            if line.auto_generated:
                existing_hours[key] = (line.hour_from, line.hour_to)
            else:
                manual_line_dates.add(key)

        # Week-level default hours (used when no per-line value found)
        week_defaults = {
            '1': (self.rotation_week_1_default_hour_from, self.rotation_week_1_default_hour_to),
            '2': (self.rotation_week_2_default_hour_from, self.rotation_week_2_default_hour_to),
            '3': (self.rotation_week_3_default_hour_from, self.rotation_week_3_default_hour_to),
            '4': (self.rotation_week_4_default_hour_from, self.rotation_week_4_default_hour_to),
        }

        lines_vals_by_week = {'1': [], '2': [], '3': [], '4': []}
        for _week_idx, date_from, date_to, _period in self._get_rotation_week_data():
            if not date_from or not date_to:
                continue

            bucket = str(_week_idx)
            default_h_from, default_h_to = week_defaults[bucket]
            current = date_from
            while current <= date_to:
                dayofweek = str(current.weekday())
                key = (bucket, current)
                if key in manual_line_dates:
                    current += timedelta(days=1)
                    continue
                if current.weekday() == 4:
                    current += timedelta(days=1)
                    continue
                hour_from, hour_to = existing_hours.get(key, (default_h_from, default_h_to))
                lines_vals_by_week[bucket].append({
                    'name': f'Shift Rotation {bucket}',
                    'dayofweek': dayofweek,
                    'hour_from': hour_from,
                    'hour_to': hour_to,
                    'day_period': 'morning',
                    'date_from': current,
                    'date_to': current,
                    'is_shift_rotation_line': True,
                    'auto_generated': True,
                    'shift_rotation_week': bucket,
                })
                current += timedelta(days=1)
        return lines_vals_by_week

    # ─────────────────────────────────────────────────────────────────────────
    # Onchange — one handler per week so only that week’s grid is touched
    # ─────────────────────────────────────────────────────────────────────────

    @api.onchange('rotation_week_1_from', 'rotation_week_1_to', 'rotation_week_1_period')
    def _onchange_week_1_generate_lines(self):
        for calendar in self:
            if not calendar.shift_rotation:
                continue
            vals = calendar._prepare_shift_rotation_line_vals()
            calendar.rotation_week_1_attendance_line_ids = calendar._build_week_onchange_commands('1', vals['1'])

    @api.onchange('rotation_week_2_from', 'rotation_week_2_to', 'rotation_week_2_period')
    def _onchange_week_2_generate_lines(self):
        for calendar in self:
            if not calendar.shift_rotation:
                continue
            vals = calendar._prepare_shift_rotation_line_vals()
            calendar.rotation_week_2_attendance_line_ids = calendar._build_week_onchange_commands('2', vals['2'])

    @api.onchange('rotation_week_3_from', 'rotation_week_3_to', 'rotation_week_3_period')
    def _onchange_week_3_generate_lines(self):
        for calendar in self:
            if not calendar.shift_rotation:
                continue
            vals = calendar._prepare_shift_rotation_line_vals()
            calendar.rotation_week_3_attendance_line_ids = calendar._build_week_onchange_commands('3', vals['3'])

    @api.onchange('rotation_week_4_from', 'rotation_week_4_to', 'rotation_week_4_period')
    def _onchange_week_4_generate_lines(self):
        for calendar in self:
            if not calendar.shift_rotation:
                continue
            vals = calendar._prepare_shift_rotation_line_vals()
            calendar.rotation_week_4_attendance_line_ids = calendar._build_week_onchange_commands('4', vals['4'])

    # ─────────────────────────────────────────────────────────────────────────
    # Onchange — bulk-apply default hours to all lines in the week
    # ─────────────────────────────────────────────────────────────────────────

    @api.onchange('rotation_week_1_default_hour_from', 'rotation_week_1_default_hour_to')
    def _onchange_week_1_default_hours(self):
        for calendar in self:
            h_from = calendar.rotation_week_1_default_hour_from
            h_to = calendar.rotation_week_1_default_hour_to
            for line in calendar.rotation_week_1_attendance_line_ids:
                line.hour_from = h_from
                line.hour_to = h_to

    @api.onchange('rotation_week_2_default_hour_from', 'rotation_week_2_default_hour_to')
    def _onchange_week_2_default_hours(self):
        for calendar in self:
            h_from = calendar.rotation_week_2_default_hour_from
            h_to = calendar.rotation_week_2_default_hour_to
            for line in calendar.rotation_week_2_attendance_line_ids:
                line.hour_from = h_from
                line.hour_to = h_to

    @api.onchange('rotation_week_3_default_hour_from', 'rotation_week_3_default_hour_to')
    def _onchange_week_3_default_hours(self):
        for calendar in self:
            h_from = calendar.rotation_week_3_default_hour_from
            h_to = calendar.rotation_week_3_default_hour_to
            for line in calendar.rotation_week_3_attendance_line_ids:
                line.hour_from = h_from
                line.hour_to = h_to

    @api.onchange('rotation_week_4_default_hour_from', 'rotation_week_4_default_hour_to')
    def _onchange_week_4_default_hours(self):
        for calendar in self:
            h_from = calendar.rotation_week_4_default_hour_from
            h_to = calendar.rotation_week_4_default_hour_to
            for line in calendar.rotation_week_4_attendance_line_ids:
                line.hour_from = h_from
                line.hour_to = h_to

    def _get_shift_rotation_lines_in_range(self, start_date, end_date):
        self.ensure_one()
        week_lines = (
                self.rotation_week_1_attendance_line_ids
                | self.rotation_week_2_attendance_line_ids
                | self.rotation_week_3_attendance_line_ids
                | self.rotation_week_4_attendance_line_ids
        )
        return week_lines.filtered(
            lambda line: line.is_shift_rotation_line
                         and line.date_from and line.date_to
                         and line.date_from <= end_date
                         and line.date_to >= start_date
        )
