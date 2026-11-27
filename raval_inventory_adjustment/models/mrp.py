from odoo import models, fields , api
from odoo.exceptions import ValidationError
class MrpWorkorder(models.Model):
    _inherit = 'mrp.workorder'

    duration = fields.Float(
     'Real Duration', compute='_compute_duration', inverse='_set_duration',
     readonly=False, store=True, copy=False , required=True)
    
    
    @api.constrains('duration')
    def _check_duration(self):
        for workorder in self:
            if workorder.duration <= 0:
                raise ValidationError("Duration cannot be zero or negative.")
    