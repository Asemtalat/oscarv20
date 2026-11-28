from odoo import api, fields, models


class ResourceCalendarAttendance(models.Model):
    _inherit = 'resource.calendar.attendance'

    is_shift_rotation_line = fields.Boolean(
        string='Shift Rotation Line',
        default=False,
        copy=False,
        help='Technical flag to identify lines generated from shift rotation.',
    )
    shift_rotation_week = fields.Selection(
        selection=[
            ('1', 'Week 1'),
            ('2', 'Week 2'),
            ('3', 'Week 3'),
            ('4', 'Week 4'),
        ],
        string='Shift Rotation Week',
        copy=False,
        help='Technical field indicating the week bucket of generated shift rotation lines.',
    )

    @staticmethod
    def _default_shift_rotation_name(vals):
        week = vals.get('shift_rotation_week') or 'line'
        date_from = vals.get('date_from')
        return f"Shift Rotation {week}{f' - {date_from}' if date_from else ''}"

    '''def _prepare_shift_rotation_vals(self, vals):
        if not vals.get('name'):
            if vals.get('is_shift_rotation_line'):
                vals['name'] = self._default_shift_rotation_name(vals)
            else:
                vals['name'] = 'Working Time'
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [self._prepare_shift_rotation_vals(dict(vals)) for vals in vals_list]
        return super().create(vals_list)'''
