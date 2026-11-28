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

from odoo import fields, models


class HrVersion(models.Model):
    """Odoo 20 has no ``hr.contract`` model: the contract is carried by the
    contract dates of ``hr.version``. The attendance settings that used to
    live on the contract now live on the version."""
    _inherit = 'hr.version'

    att_policy_id = fields.Many2one('hr.attendance.policy',
                                    string='Attendance Policy',
                                    groups='hr.group_hr_user',
                                    tracking=True)
    auto_attendance_sheet = fields.Boolean('Auto Generate Attendance Sheet',
                                           groups='hr.group_hr_user',
                                           tracking=True)

    def _get_whitelist_fields_from_template(self):
        return super()._get_whitelist_fields_from_template() + [
            'att_policy_id', 'auto_attendance_sheet']
