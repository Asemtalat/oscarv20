# -*- coding: utf-8 -*-

##############################################################################
#    Copyright (C) 2020.
#    Author: Eng.Ramadan Khalil (<rkhalil1990@gmail.com>)
#    website': https://www.linkedin.com/in/ramadan-khalil-a7088164
#
#    It is forbidden to publish, distribute, sublicense, or sell copies
#    of the Software or modified copies of the Software.
##############################################################################

from zoneinfo import ZoneInfo

from odoo import models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    def _get_employee_tz(self):
        self.ensure_one()
        return ZoneInfo(self.tz or self.env.user.tz or 'UTC')

    def _get_attendance_version(self, date_from, date_to):
        """Return the version (one record) that represents the employee's
        contract on ``[date_from, date_to]``: the version in effect at the end
        of the period for the first overlapping contract. Empty recordset if
        the employee has no contract overlapping the period."""
        self.ensure_one()
        versions = self._get_contracts(date_from, date_to).get(self.id)
        return versions[:1] if versions else self.env['hr.version']
