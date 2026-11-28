from odoo import api, fields, models
from odoo.tools import formatLang



class Picking(models.Model):
    _inherit = "stock.picking"

    show_validate_btn = fields.Boolean(compute='_compute_btn_visibility')
    def  _compute_btn_visibility(self):
        for rec in self:
            rec.show_validate_btn = True
            quality_point = self.env['quality.point'].search([], limit=1).picking_type_ids
            if rec.picking_type_id in quality_point:
                if rec.check_ids:
                    for check in rec.check_ids:
                        if check.quality_state != 'pass':
                            rec.show_validate_btn = False
                            break
                else:
                    rec.show_validate_btn = False

