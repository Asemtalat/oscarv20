# -*- coding: utf-8 -*-

##############################################################################
#
#
#    Copyright (C) 2020-TODAY .
#    Author: Eng.Ramadan Khalil (<rkhalil1990@gmail.com>)
#
#    It is forbidden to publish, distribute, sublicense, or sell copies
#    of the Software or modified copies of the Software.
#
##############################################################################

from datetime import datetime, date, timedelta, time, UTC
from dateutil.relativedelta import relativedelta
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.fields import Command, Domain
from odoo.tools.date_utils import float_to_time
from odoo.tools.misc import format_date
from .utils import time_to_float, tz_localize, interval_to_float
import logging

# from odoo import models, api, _logger
_logger = logging.getLogger(__name__)
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
TIME_FORMAT = "%H:%M:%S"


class AttendanceSheet(models.Model):
    _name = 'attendance.sheet'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Hr Attendance Sheet'

    first_day_of_month = fields.Integer(
        string='First Day of Month',
        help='Specify the first day of the attendance month (e.g., 1 for 1st, 26 for 26th).',
        default=1)
    name = fields.Char("name")
    employee_id = fields.Many2one(comodel_name='hr.employee', string='Employee',
                                  required=True)

    batch_id = fields.Many2one(comodel_name='attendance.sheet.batch',
                               string='Attendance Sheet Batch')
    department_id = fields.Many2one(related='employee_id.department_id',
                                    string='Department', store=True)
    company_id = fields.Many2one('res.company', string='Company', readonly=True,
                                 copy=False, required=True,
                                 default=lambda self: self.env.company)
    date_from = fields.Date(string='Date From', readonly=True, required=True,
                            default=lambda self: fields.Date.to_string(
                                date.today().replace(day=1)), )
    date_to = fields.Date(string='Date To', readonly=True, required=True,
                          default=lambda self: fields.Date.to_string(
                              (datetime.now() + relativedelta(months=+1, day=1,
                                                              days=-1)).date()))
    line_ids = fields.One2many(comodel_name='attendance.sheet.line',
                               string='Attendances', readonly=True,
                               inverse_name='att_sheet_id')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirm', 'Confirmed'),
        ('done', 'Approved')], default='draft', tracking=True,
        string='Status', required=True, readonly=True, index=True,
        help=' * The \'Draft\' status is used when a HR user is creating a new  attendance sheet. '
             '\n* The \'Confirmed\' status is used when  attendance sheet is confirmed by HR user.'
             '\n* The \'Approved\' status is used when  attendance sheet is accepted by the HR Manager.')
    no_overtime = fields.Integer(compute="_compute_sheet_total",
                                 string="No of overtimes", readonly=True,
                                 store=True)
    tot_overtime = fields.Float(compute="_compute_sheet_total",
                                string="Total Over Time", readonly=True,
                                store=True)
    tot_difftime = fields.Float(compute="_compute_sheet_total",
                                string="Total Diff time Hours", readonly=True,
                                store=True)
    no_unpaid_leave = fields.Float(compute="_compute_sheet_total",
                                   string="No Unpaid Leave Times", readonly=True,
                                   store=True)
    tot_unpaid_leave = fields.Float(compute="_compute_sheet_total",
                                    string="Total Unpaid Leave", readonly=True,
                                    store=True)
    no_difftime = fields.Integer(compute="_compute_sheet_total",
                                 string="No of Diff Times", readonly=True,
                                 store=True)
    tot_late = fields.Float(compute="_compute_sheet_total",
                            string="Total Late In", readonly=True, store=True)
    no_late = fields.Integer(compute="_compute_sheet_total",
                             string="No of Lates",
                             readonly=True, store=True)
    no_absence = fields.Integer(compute="_compute_sheet_total",
                                string="No of Absence Days", readonly=True,
                                store=True)
    tot_absence = fields.Float(compute="_compute_sheet_total",
                               string="Total absence Hours", readonly=True,
                               store=True)
    tot_worked_hour = fields.Float(compute="_compute_sheet_total",
                                   string="Total Late In", readonly=True,
                                   store=True)
    att_policy_id = fields.Many2one(comodel_name='hr.attendance.policy',
                                    string="Attendance Policy ", required=True)
    payslip_id = fields.Many2one(comodel_name='hr.payslip', string='PaySlip')

    version_id = fields.Many2one('hr.version', string='Contract Version',
                                 readonly=False)

    unattended_days = fields.Integer(string="Number of Unattended Days", compute="_compute_sheet_total", readonly=True,
                                     store=True)
    attendance_count = fields.Integer(string="Number of Attended Days", compute="_compute_sheet_total", readonly=True,
                                      store=True)
    no_diff_days = fields.Integer(string="No of Diff Days", compute="_compute_diff_days", readonly=True, store=True)
    can_approve = fields.Boolean(compute='_compute_can_approve', string='Can Approve')

    @api.depends_context('uid')
    @api.depends('employee_id.parent_id.user_id')
    def _compute_can_approve(self):
        for sheet in self:
            can_approve = False
            if self.env.user.has_group('rm_hr_attendance_sheet.group_attendance_sheet_manager'):
                can_approve = True
            elif self.env.user.has_group(
                    'rm_hr_attendance_sheet.group_attendance_sheet_leader') and sheet.employee_id.parent_id.user_id.id == self.env.user.id:
                can_approve = True
            sheet.can_approve = can_approve

    @api.depends('date_from', 'date_to', 'version_id.contract_date_start',
                 'version_id.contract_date_end')
    def _compute_diff_days(self):
        """Number of days of the sheet period that fall outside the contract."""
        for sheet in self:
            sheet.no_diff_days = 0
            version = sheet.version_id
            if not version and sheet.employee_id and sheet.date_from and sheet.date_to:
                version = sheet.employee_id._get_attendance_version(
                    sheet.date_from, sheet.date_to)
            if not version or not version.contract_date_start \
                    or not sheet.date_from or not sheet.date_to:
                continue
            days = 0
            if version.contract_date_start > sheet.date_from:
                days += (min(version.contract_date_start, sheet.date_to + timedelta(days=1))
                         - sheet.date_from).days
            if version.contract_date_end and version.contract_date_end < sheet.date_to:
                days += (sheet.date_to - max(version.contract_date_end,
                                             sheet.date_from - timedelta(days=1))).days
            sheet.no_diff_days = max(days, 0)

    def unlink(self):
        if any(self.filtered(
                lambda att: att.state not in ('draft', 'confirm'))):
            # TODO:un comment validation in case on non testing
            pass
            # raise UserError(_(
            #     'You cannot delete an attendance sheet which is '
            #     'not draft or confirmed!'))
        return super(AttendanceSheet, self).unlink()

    @api.constrains('date_from', 'date_to')
    def check_date(self):
        for sheet in self:
            emp_sheets = self.env['attendance.sheet'].search(
                [('employee_id', '=', sheet.employee_id.id),
                 ('id', '!=', sheet.id)])
            for emp_sheet in emp_sheets:
                if max(sheet.date_from, emp_sheet.date_from) < min(
                        sheet.date_to, emp_sheet.date_to):
                    raise UserError(_(
                        'You Have Already Attendance Sheet For That '
                        'Period  Please pick another date !'))

    def _cron_update_attendance_sheet(self, shift_days=0):
        today = date.today()
        start_month = today + relativedelta(day=1, days=shift_days)
        sheet_ids = self.search(
            [('date_from', '=', start_month),
             ('state', '=', 'draft')])
        for sheet in sheet_ids:
            sheet._action_get_attendance()

    def _cron_generate_attendance_sheet(self):
        _logger.info("Starting monthly attendance sheet generation...")

        today = date.today()
        company = self.env.company
        first_day_of_month = company.first_day_of_month
        if first_day_of_month != 1:
            if today.day < first_day_of_month:
                start_month = (today + relativedelta(day=first_day_of_month)) - relativedelta(months=1)
                end_month = today + relativedelta(day=first_day_of_month - 1)
            else:
                start_month = today + relativedelta(day=first_day_of_month)
                end_month = today + relativedelta(months=1, day=first_day_of_month - 1)
        else:
            start_month = today + relativedelta(day=1)
            end_month = today + relativedelta(months=1, day=1, days=-1)

        _logger.info("Start month: %s, End month: %s", start_month, end_month)

        # Odoo 20: running contracts are versions that are "in contract".
        versions = self.env['hr.version'].search(Domain.AND([
            self.env['hr.version']._get_current_versions_domain(),
            [('employee_id', '!=', False),
             ('auto_attendance_sheet', '=', True),
             ('att_policy_id', '!=', False)],
        ]))
        _logger.info("Found %s versions eligible for attendance sheet generation.", len(versions))

        for employee in versions.employee_id:
            try:
                _logger.info("Processing attendance sheet for employee %s", employee.name)

                attendance_sheet_id = self.env['attendance.sheet'].search([
                    ('employee_id', '=', employee.id),
                    ('date_from', '=', start_month),
                    ('date_to', '=', end_month)
                ], limit=1)

                if attendance_sheet_id:
                    _logger.info("Attendance sheet already exists for employee %s for period %s - %s",
                                 employee.name, start_month, end_month)
                    continue

                new_sheet = self.env['attendance.sheet'].new({
                    'employee_id': employee.id,
                    'date_from': start_month,
                    'date_to': end_month,
                })
                new_sheet.onchange_employee()
                values = self.env['attendance.sheet']._convert_to_write(new_sheet._cache)

                if not values.get('att_policy_id'):
                    _logger.warning("No Attendance Policy for Employee %s", employee.name)
                    continue

                att_sheet_id = self.env['attendance.sheet'].create(values)
                att_sheet_id._action_get_attendance()
                _logger.info("Attendance sheet created successfully for employee %s", employee.name)

            except Exception as e:
                _logger.warning("Error while creating monthly attendance sheet for employee %s: %s", employee.name, e)

        _logger.info("Monthly attendance sheet generation completed.")

    def action_confirm(self):
        self.write({'state': 'confirm'})

    def action_approve(self):
        self.action_create_payslip()
        self.write({'state': 'done'})

    def action_draft(self):
        self.write({'state': 'draft'})

    @api.onchange('employee_id', 'date_from', 'date_to')
    def onchange_employee(self):
        if not self.employee_id or not self.date_from or not self.date_to:
            return
        employee = self.employee_id
        date_from = self.date_from
        date_to = self.date_to
        if self.company_id.first_day_of_month != 1:
            display_month = date_from + relativedelta(months=1)
        else:
            display_month = date_from
        self.name = 'Attendance Sheet - %s - %s' % (
            self.employee_id.name or '',
            format_date(self.env, display_month, date_format="MMMM y")
        )
        self.company_id = employee.company_id
        version = employee._get_attendance_version(date_from, date_to)
        if not version:
            raise ValidationError(_('There Is No Valid Contract For Employee %s', employee.name))
        self.version_id = version
        if not version.att_policy_id:
            raise ValidationError(_('Employee %s does not have attendance policy', employee.name))
        self.att_policy_id = version.att_policy_id

    @api.depends('date_from', 'date_to', 'line_ids.overtime', 'line_ids.diff_time',
                 'line_ids.late_in', 'line_ids.status', 'line_ids.unpaid_leave',
                 'line_ids.worked_hours', 'line_ids.date')
    def _compute_sheet_total(self):
        """
        Compute Total overtime,late ,absence,diff time and worked hours
        :return:
        """
        for sheet in self:
            # Compute Total Overtime
            unpaid_leaves = sheet.line_ids.filtered(lambda l: l.status == 'leave' and l.unpaid_leave == True)
            sheet.no_unpaid_leave = len(unpaid_leaves)
            sheet.tot_unpaid_leave = sum([l.unpaid_leave for l in unpaid_leaves])
            overtime_lines = sheet.line_ids.filtered(lambda l: l.overtime > 0)
            sheet.tot_overtime = sum([l.overtime for l in overtime_lines])
            sheet.no_overtime = len(overtime_lines)
            # Compute Total Late In
            late_lines = sheet.line_ids.filtered(lambda l: l.late_in > 0)
            sheet.tot_late = sum([l.late_in for l in late_lines])
            sheet.no_late = len(late_lines)
            # Compute Absence
            absence_lines = sheet.line_ids.filtered(
                lambda l: l.diff_time > 0 and l.status == "ab")
            sheet.tot_absence = sum([l.diff_time for l in absence_lines])
            sheet.no_absence = len(absence_lines)
            diff_lines = sheet.line_ids.filtered(
                lambda l: l.diff_time > 0 and l.status != "ab")
            sheet.tot_difftime = sum([l.diff_time for l in diff_lines])
            sheet.no_difftime = len(diff_lines)

            from_date = sheet.date_from
            to_date = sheet.date_to
            all_dates = [(from_date + timedelta(days=x)) for x in
                         range((to_date - from_date).days + 1)]
            uwd_cnt = 0
            wd_cnt = 0
            for day in all_dates:
                day_lines = sheet.line_ids.filtered(
                    lambda l:
                    l.date == day and
                    (l.status in ['leave', 'ph', 'ab'])
                )
                if day_lines:
                    uwd_cnt += 1
            sheet.unattended_days = uwd_cnt

            for day in all_dates:
                day_lines = sheet.line_ids.filtered(
                    lambda l: l.date == day and (l.worked_hours > 0))
                if day_lines:
                    wd_cnt += 1
            sheet.attendance_count = wd_cnt

    def _get_float_from_time(self, time):
        str_time = datetime.strftime(time, "%H:%M")
        split_time = [int(n) for n in str_time.split(":")]
        float_time = split_time[0] + split_time[1] / 60.0
        return float_time

    def _is_shift_rotation_calendar(self, calendar_id):
        return bool(calendar_id and 'shift_rotation' in calendar_id._fields and calendar_id.shift_rotation)

    def _get_shift_rotation_day_lines(self, calendar_id, day):
        """Return the configured shift lines for the exact day.

        The lookup is date-driven, not weekday-driven:
        1. Find the rotation week that contains the current day.
        2. Read the exact shift lines for that day within that week.

        If the day exists in a configured week and has hours, it is treated
        as a working day even if it is Saturday. Friday is considered a
        weekend only when no working hours are configured for that date.
        """
        self.ensure_one()
        if not self._is_shift_rotation_calendar(calendar_id):
            return self.env['resource.calendar.shift.line']

        week_bucket = self._get_rotation_week_for_day(calendar_id, day)
        if not week_bucket:
            return self.env['resource.calendar.shift.line']

        return self.env['resource.calendar.shift.line'].search([
            ('calendar_id', '=', calendar_id.id),
            ('shift_rotation_week', '=', week_bucket),
            ('date_from', '<=', day),
            ('date_to', '>=', day),
            ('dayofweek', '=', str(day.weekday())),
            ('day_period', '!=', 'lunch'),
        ], order='hour_from asc')

    def _get_day_work_intervals(self, calendar_id, day, tz):
        """Return planned work intervals for one day as UTC-naive tuples."""
        day_start = datetime.combine(day, time.min)
        day_end = datetime.combine(day, time.max)

        # Shift rotation calendars store one date-specific schedule line per day.
        if self._is_shift_rotation_calendar(calendar_id):
            rotation_lines = self._get_shift_rotation_day_lines(calendar_id, day).filtered(
                lambda l: l.hour_to > l.hour_from
            )
            intervals = []
            for line in rotation_lines:
                local_start = datetime.combine(day, float_to_time(line.hour_from)).replace(tzinfo=tz)
                local_end = datetime.combine(day, float_to_time(line.hour_to)).replace(tzinfo=tz)
                intervals.append((
                    local_start.astimezone(UTC).replace(tzinfo=None),
                    local_end.astimezone(UTC).replace(tzinfo=None),
                ))
            return calendar_id.att_interval_clean(intervals)

        return calendar_id.att_get_work_intervals(self, day_start, day_end, tz)

    def _get_overtime_values(self, policy_id, ot_type, ot_intervals):
        """Compute overtime from attendance intervals, using policy when available."""
        act_overtime = 0.0
        for ot in ot_intervals:
            if ot[1] > ot[0]:
                act_overtime += interval_to_float(ot)

        calc_overtime = act_overtime
        overtime_rules = policy_id.overtime_rule_ids.filtered(lambda r: r.type == ot_type)
        if overtime_rules:
            act_overtime, calc_overtime = policy_id.get_overtime(ot_type=ot_type, ot_intervals=ot_intervals)
        return act_overtime, calc_overtime

    def get_attendance_intervals(self, employee, day_start, day_end, tz):
        """

        :param employee:
        :param day_start:datetime the start of the day in datetime format
        :param day_end: datetime the end of the day in datetime format
        :return:
        """
        day_start_native = day_start.replace(tzinfo=tz).astimezone(
            UTC).replace(tzinfo=None)
        day_end_native = day_end.replace(tzinfo=tz).astimezone(
            UTC).replace(tzinfo=None)
        res = []
        attendances = self.env['hr.attendance'].sudo().search(
            [('employee_id', '=', employee.id),
             ('check_in', '<=', day_end_native),
             '|', ('check_out', '=', False), ('check_out', '>=', day_start_native)],
            order="check_in")
        for att in attendances:
            check_in = att.check_in
            check_out = att.check_out
            if not check_out:
                continue
            interval_start = max(check_in, day_start_native)
            interval_end = min(check_out, day_end_native)
            if interval_start < interval_end:
                res.append((interval_start, interval_end))
        return res

    def _get_emp_leave_intervals(self, employee_id, day_start, day_end, wk_intervals):
        leave_obj = self.env['hr.leave']

        # Update the search domain to remove 'holiday_type'
        leave_ids = leave_obj.search([
            ('state', '=', 'validate'),
            ('employee_id', '=', employee_id.id),
            ('request_date_from', '<=', day_end.date()),
            ('request_date_to', '>=', day_start.date())
        ])

        leave_intervals = []
        for leave in leave_ids:
            leave_intervals.append((leave.date_from, leave.date_to))

        return leave_intervals


    def get_public_holiday(self, date, emp):
        public_holiday = []
        public_holidays = self.env['hr.public.holiday'].sudo().search(
            [('date_from', '<=', date), ('date_to', '>=', date),
             ('state', '=', 'active')])
        for ph in public_holidays:
            if not ph.emp_ids:
                return public_holidays
            if emp.id in ph.emp_ids.ids:
                public_holiday.append(ph.id)
        return public_holiday

    def action_get_attendance(self):
        for sheet in self:
            self._action_get_attendance()

    def _pre_get_attendance(self):
        self.ensure_one()
        self.line_ids.unlink(allow_action=True)

    def _create_ph_lines(self, day, tz, policy_id, att_intervals):
        self.ensure_one()
        ot_type = 'ph'
        day_str = day.strftime('%A')
        att_lines = []
        if att_intervals:
            for att_interval in att_intervals:
                act_overtime, calc_overtime = self._get_overtime_values(
                    policy_id=policy_id,
                    ot_type=ot_type,
                    ot_intervals=[att_interval],
                )
                ac_sign_in = time_to_float(tz_localize(att_interval[0], tz))
                worked_hours = interval_to_float(att_interval)
                ac_sign_out = ac_sign_in + worked_hours
                values = {
                    'date': day,
                    'day': str(day.weekday()),
                    'ac_sign_in': ac_sign_in,
                    'ac_sign_out': ac_sign_out,
                    'worked_hours': worked_hours,
                    'overtime': calc_overtime,
                    'act_overtime': act_overtime,
                    'att_sheet_id': self.id,
                    'status': 'ph',
                    'note': _("working on Public Holiday")
                }
                att_lines.append(values)
        else:
            values = {
                'date': day,
                'day': str(day.weekday()),
                'att_sheet_id': self.id,
                'status': 'ph',
            }
            att_lines.append(values)
        line_ids = self.env['attendance.sheet.line'].create(att_lines)
        return line_ids

    def _create_we_lines(self, day, tz, policy_id, att_intervals):
        self.ensure_one()
        ot_type = 'we'
        day_str = day.strftime('%A')
        day_number = day.weekday()
        att_lines = []
        if att_intervals:
            for att_interval in att_intervals:
                act_overtime, calc_overtime = self._get_overtime_values(
                    policy_id=policy_id,
                    ot_type=ot_type,
                    ot_intervals=[att_interval],
                )
                ac_sign_in = time_to_float(tz_localize(att_interval[0], tz))
                worked_hours = interval_to_float(att_interval)
                ac_sign_out = ac_sign_in + worked_hours
                values = {
                    'date': day,
                    'day': str(day_number),
                    'ac_sign_in': ac_sign_in,
                    'ac_sign_out': ac_sign_out,
                    'overtime': calc_overtime,
                    'act_overtime': act_overtime,
                    'worked_hours': worked_hours,
                    'att_sheet_id': self.id,
                    'status': 'weekend',
                    'note': _("working in weekend")
                }
                att_lines.append(values)
        else:
            values = {
                'date': day,
                'day': str(day_number),
                'att_sheet_id': self.id,
                'status': 'weekend',
                'note': ""
            }
            att_lines.append(values)
        line_ids = self.env['attendance.sheet.line'].create(att_lines)
        return line_ids

    def _create_wd_lines(self, day, tz, policy_id, calendar_id, late_cnt, diff_cnt, leaves, wk_interval,
                             att_wk_intervals):
        self.ensure_one()
        pl_sign_in = time_to_float(tz_localize(wk_interval[0], tz))
        pl_work_hours = interval_to_float(wk_interval)
        pl_sign_out = pl_sign_in + pl_work_hours
        worked_hours = 0
        diff_intervals = []
        ot_type = 'wd'
        status = ""
        note = ""
        act_late = 0
        act_diff = 0
        day_str = day.strftime('%A')
        ac_sign_in = time_to_float(tz_localize(att_wk_intervals[0][0], tz))

        start_time = tz_localize(att_wk_intervals[0][0], tz)
        end_time = tz_localize(att_wk_intervals[-1][1], tz)
        time_difference = end_time - start_time
        tot_wk_hours = time_difference.total_seconds() / 3600

        ac_sign_out = ac_sign_in + tot_wk_hours

        late_interval = (wk_interval[0], att_wk_intervals[0][0])
        ot_interval = (wk_interval[1], att_wk_intervals[-1][1])

        if ot_interval[1] < ot_interval[0] and len(att_wk_intervals) == 1:
            diff_intervals.append((ot_interval[1], ot_interval[0]))
        if len(att_wk_intervals) > 1:
            remain_interval = (att_wk_intervals[0][1], wk_interval[1])
            for att_wk_interval in att_wk_intervals:
                worked_hours += interval_to_float(att_wk_interval)
                if att_wk_interval[1] <= remain_interval[0]:
                    continue
                if att_wk_interval[0] >= remain_interval[1]:
                    break
                if remain_interval[0] < att_wk_interval[0] < remain_interval[1]:
                    diff_intervals.append((remain_interval[0], att_wk_interval[0]))
                    remain_interval = (att_wk_interval[1], remain_interval[1])
            if remain_interval and remain_interval[0] <= wk_interval[1]:
                diff_intervals.append((remain_interval[0], wk_interval[1]))
        else:
            worked_hours = interval_to_float(att_wk_intervals[0])

        if leaves:
            status = "leave"
            # get the diff time for the leave
            for diff_interval in diff_intervals:
                df_intervals = calendar_id.att_interval_without_leaves(diff_interval, leaves)
                for df_interval in df_intervals:
                    act_diff += interval_to_float(df_interval)
            # get the late time for the leave
            lt_intervals = calendar_id.att_interval_without_leaves(late_interval, leaves)
            for lt_interval in lt_intervals:
                act_late += interval_to_float(lt_interval)
        else:
            act_late = interval_to_float(late_interval)
            act_diff = sum([interval_to_float(df_interval) for df_interval in diff_intervals])
        calc_late, late_cnt = policy_id.get_late(act_late, late_cnt)
        calc_diff, diff_cnt = policy_id.get_diff(act_diff, diff_cnt)
        act_overtime, calc_overtime = self._get_overtime_values(
            policy_id=policy_id,
            ot_type=ot_type,
            ot_intervals=[ot_interval],
        )

        # Detect unpaid leave on this day (any overlapping validated leave type marked as unpaid)
        is_unpaid_leave = False
        if status == 'leave':
            day_start = datetime.combine(day, time.min)
            day_end = datetime.combine(day, time.max)
            leave_recs = self.env['hr.leave'].search([
                ('state', '=', 'validate'),
                ('employee_id', '=', self.employee_id.id),
                ('request_date_from', '<=', day_end.date()),
                ('request_date_to', '>=', day_start.date()),
            ], limit=1)
            if leave_recs:
                is_unpaid_leave = any(l.work_entry_type_id.unpaid for l in leave_recs)

        values = {
            'date': day,
            'day': str(day.weekday()),
            'pl_sign_in': pl_sign_in,
            'pl_sign_out': pl_sign_out,
            'ac_sign_in': ac_sign_in,
            'ac_sign_out': ac_sign_out,
            'late_in': calc_late,
            'act_late_in': act_late,
            'worked_hours': worked_hours,
            'overtime': calc_overtime,
            'act_overtime': act_overtime,
            'diff_time': calc_diff,
            'act_diff_time': act_diff,
            'status': status,
            'att_sheet_id': self.id,
            'note': note,
            'unpaid_leave': is_unpaid_leave,
        }
        wd_line_id = self.env['attendance.sheet.line'].create(values)
        return wd_line_id, late_cnt, diff_cnt

    def _create_ab_lines(self, day, tz, policy_id, calendar_id, abs_cnt, leaves, wk_interval):
        self.ensure_one()
        day_str = day.strftime('%A')
        day_number = day.weekday()
        pl_sign_in = time_to_float(tz_localize(wk_interval[0], tz))
        pl_work_hours = interval_to_float(wk_interval)
        pl_sign_out = pl_sign_in + pl_work_hours
        status = ""
        note = ""
        abs_flag = False
        act_diff = 0
        unpaid_leave = False
        if not self.employee_id._is_in_contract(day):
            note = "Out Of Contract Days"
        else:
            diff_interval = (
                (wk_interval[0], wk_interval[1]))
            if leaves:
                status = "leave"
                # Determine unpaid leave by checking overlapping validated leaves for this day
                day_start = datetime.combine(day, time.min)
                day_end = datetime.combine(day, time.max)
                leave_recs = self.env['hr.leave'].search([
                    ('state', '=', 'validate'),
                    ('employee_id', '=', self.employee_id.id),
                    ('request_date_from', '<=', day_end.date()),
                    ('request_date_to', '>=', day_start.date()),
                ])
                unpaid_leave = any(l.work_entry_type_id.unpaid for l in leave_recs)
                # get the diff time for the leave
                df_intervals = calendar_id.att_interval_without_leaves(diff_interval, leaves)
                for df_interval in df_intervals:
                    act_diff += interval_to_float(df_interval)
            else:
                status = "ab"
                act_diff = interval_to_float(diff_interval)
        if status == 'ab':
            if not abs_flag:
                abs_cnt += 1
            abs_flag = True
        calc_diff = policy_id.get_absence(act_diff, abs_cnt)
        values = {
            'date': day,
            'day': str(day_number),
            'pl_sign_in': pl_sign_in,
            'pl_sign_out': pl_sign_out,
            'diff_time': calc_diff,
            'act_diff_time': act_diff,
            'status': status,
            'att_sheet_id': self.id,
            'unpaid_leave': unpaid_leave,
            'note': note
        }
        abs_line_id = self.env['attendance.sheet.line'].create(values)
        return abs_line_id, abs_cnt

    def _create_out_wk_lines(self, day, tz, policy_id, out_wk_intervals):
        self.ensure_one()
        ot_type = 'wd'
        day_str = day.strftime('%A')
        note = _("overtime out of work intervals")
        att_lines = []
        for att_out in out_wk_intervals:
            ot_interval = (att_out[0], att_out[1])
            ac_sign_in = time_to_float(tz_localize(att_out[0], tz))
            work_hours = interval_to_float(att_out)
            ac_sign_out = ac_sign_in + work_hours
            act_overtime, calc_overtime = self._get_overtime_values(
                policy_id=policy_id,
                ot_type=ot_type,
                ot_intervals=[ot_interval],
            )
            values = {
                'date': day,
                'day': str(day.weekday()),
                'pl_sign_in': 0,
                'pl_sign_out': 0,
                'ac_sign_in': ac_sign_in,
                'ac_sign_out': ac_sign_out,
                'overtime': calc_overtime,
                'act_overtime': act_overtime,
                'worked_hours': work_hours,
                'note': note,
                'att_sheet_id': self.id
            }
            att_lines.append(values)
        line_ids = self.env['attendance.sheet.line'].create(att_lines)
        return line_ids

    def _float_hour_to_datetime(self, day, hour_value):
        """Convert float hour (can exceed 24) to datetime for the given day."""
        return datetime.combine(day, time.min) + timedelta(hours=hour_value or 0.0)

    def _get_rotation_week_for_day(self, calendar_id, day):
        """Return rotation week bucket ('1'..'4') for a date, or False."""
        for week_idx in (1, 2, 3, 4):
            week_from = calendar_id[f'rotation_week_{week_idx}_from']
            week_to = calendar_id[f'rotation_week_{week_idx}_to']
            if week_from and week_to and week_from <= day <= week_to:
                return str(week_idx)
        return False

    def _recompute_sheet_lines_overtime(self, line_ids, calendar_id, policy_id):
        """Overtime = max(actual worked hours - scheduled hours, 0) per sheet line."""
        for line in line_ids:
            if not line.date or line.worked_hours <= 0:
                line.write({'act_overtime': 0.0, 'overtime': 0.0})
                continue

            scheduled_hours = 0.0
            if line.pl_sign_out > line.pl_sign_in:
                scheduled_hours = line.pl_sign_out - line.pl_sign_in

            act_overtime = max(line.worked_hours - scheduled_hours, 0.0)
            line.write({
                'act_overtime': act_overtime,
                'overtime': act_overtime,
            })

    def _action_get_attendance(self):
        """
        Get Attendance for the employee
        """
        self.ensure_one()
        self._pre_get_attendance()
        employee_id = self.employee_id
        tz = employee_id._get_employee_tz()
        version_id = self.version_id
        if not version_id:
            raise ValidationError(_(
                'Please add contract to the %s `s contract ', employee_id.name))
        if not version_id.resource_calendar_id:
            raise ValidationError(_(
                'Can`t find calendar for the employee %s', employee_id.name))
        policy_id = self.att_policy_id
        if not policy_id:
            raise ValidationError(_(
                'Please add Attendance Policy to the %s `s contract ', employee_id.name))
        all_dates = [(self.date_from + timedelta(days=x)) for x in
                     range((self.date_to - self.date_from).days + 1)]
        abs_cnt = 0
        late_cnt = []
        diff_cnt = []
        att_line_ids = self.env['attendance.sheet.line']
        for day in all_dates:
            day_start = datetime.combine(day, time.min)
            day_end = datetime.combine(day, time.max)
            day_str = day.strftime('%A')
            # Odoo 20: the working schedule belongs to the version in effect
            # on each day (a schedule change creates a new version)
            calendar_id = (employee_id._get_version(day).resource_calendar_id
                           or version_id.resource_calendar_id)
            wk_intervals = self._get_day_work_intervals(calendar_id, day, tz)
            att_intervals = self.get_attendance_intervals(employee_id, day_start, day_end, tz)
            leaves = self._get_emp_leave_intervals(employee_id, day_start, day_end, wk_intervals)
            public_holiday = self.get_public_holiday(day, employee_id)
            reserved_intervals = []
            abs_flag = False
            if not wk_intervals:
                # if no work intervals then the day is Weekend
                we_line_ids = self._create_we_lines(day, tz, policy_id,
                                                    att_intervals=att_intervals)
                att_line_ids |= we_line_ids
                continue
            if public_holiday:
                # if public holiday then the day is Public Holiday
                ph_line_ids = self._create_ph_lines(day, tz, policy_id,
                                                    att_intervals=att_intervals)
                att_line_ids |= ph_line_ids
                continue
            for i, wk_interval in enumerate(wk_intervals):
                att_wk_intervals = []
                for j, att_interval in enumerate(att_intervals):
                    if max(wk_interval[0], att_interval[0]) < min(wk_interval[1], att_interval[1]):
                        if i + 1 < len(wk_intervals) and max(wk_intervals[i + 1][0], att_interval[0]) < min(
                                wk_intervals[i + 1][1], att_interval[1]):
                            att_intervals[j] = (att_interval[0], wk_intervals[i + 1][0])
                            att_intervals.insert(j + 1, (wk_intervals[i + 1][0], att_interval[1]))
                        att_wk_intervals.append(att_intervals[j])
                reserved_intervals += att_wk_intervals

                if att_wk_intervals:
                    wd_line_id, late_cnt, diff_cnt = self._create_wd_lines(
                        day=day,
                        tz=tz,
                        policy_id=policy_id,
                        calendar_id=calendar_id,
                        late_cnt=late_cnt,
                        diff_cnt=diff_cnt,
                        leaves=leaves,
                        wk_interval=wk_interval,
                        att_wk_intervals=att_wk_intervals)
                    att_line_ids |= wd_line_id
                else:
                    status = "ab"
                    abs_line_id, abs_cnt = self._create_ab_lines(
                        day=day,
                        tz=tz,
                        policy_id=policy_id,
                        calendar_id=calendar_id,
                        abs_cnt=abs_cnt,
                        leaves=leaves,
                        wk_interval=wk_interval)
                    att_line_ids |= abs_line_id
            out_wk_intervals = [x for x in att_intervals if
                                x not in reserved_intervals]
            if out_wk_intervals:
                # Update the day_end variable to reflect the actual end time of the workday
                day_end = max([x[1] for x in out_wk_intervals])
                out_line_ids = self._create_out_wk_lines(day, tz, policy_id, out_wk_intervals)
                att_line_ids |= out_line_ids
        self._recompute_sheet_lines_overtime(att_line_ids, version_id.resource_calendar_id, policy_id)
        return att_line_ids

    def action_payslip(self):
        self.ensure_one()
        payslip_id = self.payslip_id
        if not payslip_id:
            payslip_id = self.action_create_payslip()[0]
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'hr.payslip',
            'view_mode': 'form',
            'view_type': 'form',
            'res_id': payslip_id.id,
            'views': [(False, 'form')],
        }

    def action_create_payslip(self):
        payslip_obj = self.env['hr.payslip']
        payslips = payslip_obj
        for sheet in self:
            version = sheet.employee_id._get_attendance_version(sheet.date_from, sheet.date_to)
            if not version:
                raise ValidationError(_('There is no active contract for current employee'))
            if sheet.payslip_id:
                raise ValidationError(_('Payslip Has Been Created Before'))
            struct = version.structure_type_id.default_struct_id
            payslip_name = getattr(struct, 'payslip_name', False) or _('Salary Slip')
            name = '%(payslip_name)s - %(employee_name)s - %(dates)s' % {
                'payslip_name': payslip_name,
                'employee_name': sheet.employee_id.name,
                'dates': format_date(self.env, sheet.date_from, date_format="MMMM y")
            }

            payslip_id = payslip_obj.create({
                'name': name,
                'employee_id': sheet.employee_id.id,
                'date_from': sheet.date_from,
                'date_to': sheet.date_to,
                'attendance_sheet_ids': [Command.link(sheet.id)],
                'version_id': version.id,
                'struct_id': struct.id,
            })
            payslip_id.compute_sheet()
            sheet.payslip_id = payslip_id
            payslips += payslip_id
        return payslips


class AttendanceSheetLine(models.Model):
    _name = 'attendance.sheet.line'
    _description = 'Hr Attendance Sheet Line'

    state = fields.Selection([
        ('draft', 'Draft'),
        ('sum', 'Summary'),
        ('confirm', 'Confirmed'),
        ('done', 'Approved')], related='att_sheet_id.state', store=True, )

    date = fields.Date("Date")
    day = fields.Selection([
        ('0', 'Monday'),
        ('1', 'Tuesday'),
        ('2', 'Wednesday'),
        ('3', 'Thursday'),
        ('4', 'Friday'),
        ('5', 'Saturday'),
        ('6', 'Sunday')
    ], 'Day of Week', required=True, index=True, )
    att_sheet_id = fields.Many2one(comodel_name='attendance.sheet',
                                   ondelete="cascade",
                                   string='Attendance Sheet', readonly=True)
    employee_id = fields.Many2one(related='att_sheet_id.employee_id',
                                  string='Employee')
    pl_sign_in = fields.Float("Planned sign in", readonly=True)
    pl_sign_out = fields.Float("Planned sign out", readonly=True)
    worked_hours = fields.Float("Worked Hours", readonly=True)
    ac_sign_in = fields.Float("Actual sign in", readonly=True)
    ac_sign_out = fields.Float("Actual sign out", readonly=True)
    overtime = fields.Float("Overtime", readonly=True)
    act_overtime = fields.Float("Actual Overtime", readonly=True)
    late_in = fields.Float("Late In", readonly=True)
    diff_time = fields.Float("Diff Time",
                             help="Difference between the working time and attendance time(s) ",
                             readonly=True)
    act_late_in = fields.Float("Actual Late In", readonly=True)
    act_diff_time = fields.Float("Actual Diff Time",
                                 help="Difference between the working time and attendance time(s) ",
                                 readonly=True)
    status = fields.Selection(string="Status",
                              selection=[('ab', 'Absence'),
                                         ('weekend', 'Week End'),
                                         ('ph', 'Public Holiday'),
                                         ('leave', 'Leave'), ],
                              required=False, readonly=True)
    note = fields.Text("Note", readonly=True)
    unpaid_leave = fields.Boolean(string=('Unpaid Leave'), readonly=True)

    def unlink(self, allow_action=False):
        if not allow_action and not self.env.user.has_group('rm_hr_attendance_sheet.group_attendance_sheet_manager'):
            raise UserError(_('Only managers can delete attendance sheet lines.'))
        return super(AttendanceSheetLine, self).unlink()
