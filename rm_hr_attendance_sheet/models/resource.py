# -*- coding: utf-8 -*-

##############################################################################
#
#
#    Copyright (C) 2024-TODAY .
#    Author: Eng.Ramadan Khalil (<rkhalil1990@gmail.com>)
#
#    It is forbidden to publish, distribute, sublicense, or sell copies
#    of the Software or modified copies of the Software.
#
##############################################################################

from datetime import UTC
from operator import itemgetter

from odoo import models


class ResourceCalendar(models.Model):
    _inherit = "resource.calendar"

    def att_get_work_intervals(self, sheet, day_start, day_end, tz):
        """Return the planned work intervals of the calendar for one day as
        a list of ``(start, end)`` UTC-naive datetimes.

        In Odoo 20 the calendar engine natively handles recurring / dated
        attendances (multi-week rotations), duration based attendances and
        flexible calendars, so the module relies on it instead of
        re-implementing the interval generation.

        :param sheet: the attendance sheet (used to get the employee resource)
        :param day_start: naive datetime, start of the day (local time)
        :param day_end: naive datetime, end of the day (local time)
        :param tz: ``zoneinfo.ZoneInfo`` of the employee
        """
        self.ensure_one()
        start = day_start.replace(tzinfo=tz)
        end = day_end.replace(tzinfo=tz)
        resource = sheet.employee_id.resource_id if sheet and sheet.employee_id else False
        resources_per_tz = {tz: resource} if resource else None
        intervals_by_resource = self._attendance_intervals_batch(
            start, end, resources_per_tz=resources_per_tz)
        attendance_intervals = intervals_by_resource.get(
            resource.id if resource else False, [])
        working_intervals = [
            (interval[0].astimezone(UTC).replace(tzinfo=None),
             interval[1].astimezone(UTC).replace(tzinfo=None))
            for interval in attendance_intervals
        ]
        return self.att_interval_clean(working_intervals)

    def att_interval_clean(self, intervals):
        intervals = sorted(intervals, key=itemgetter(0))  # sort on first datetime
        cleaned = []
        working_interval = None
        while intervals:
            current_interval = intervals.pop(0)
            if not working_interval:  # init
                working_interval = [current_interval[0], current_interval[1]]
            elif working_interval[1] < current_interval[0]:
                cleaned.append(tuple(working_interval))
                working_interval = [current_interval[0], current_interval[1]]
            elif working_interval[1] < current_interval[1]:
                working_interval[1] = current_interval[1]
        if working_interval:
            cleaned.append(tuple(working_interval))
        return cleaned

    def att_interval_without_leaves(self, interval, leave_intervals):
        if not interval:
            return interval
        if leave_intervals is None:
            leave_intervals = []
        intervals = []
        leave_intervals = self.att_interval_clean(leave_intervals)
        current_interval = [interval[0], interval[1]]
        for leave in leave_intervals:
            if leave[1] <= current_interval[0]:
                continue
            if leave[0] >= current_interval[1]:
                break
            if current_interval[0] < leave[0] < current_interval[1]:
                current_interval[1] = leave[0]
                intervals.append((current_interval[0], current_interval[1]))
                current_interval = [leave[1], interval[1]]
            if current_interval[0] <= leave[1]:
                current_interval[0] = leave[1]
        if current_interval and current_interval[0] < interval[1]:
            # remove intervals moved outside base interval due to leaves
            intervals.append((current_interval[0], current_interval[1]))
        return intervals
