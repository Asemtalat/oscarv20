# Copyright (C) NexGen Solutions
from odoo import api, fields, models
import lxml.etree as ET

class AccessElementWizard(models.TransientModel):
    _name = 'access.element.wizard'
    _description = 'UI Element Selector Wizard'

    element_id = fields.Many2one('access.management.element', required=True, ondelete='cascade')
    choice_ids = fields.One2many('access.element.choice', 'wizard_id', string='Available Elements')
    selected_choice_id = fields.Many2one('access.element.choice', string='Selected Element', required=True)

    def action_apply(self):
        self.ensure_one()
        if self.selected_choice_id:
            self.element_id.element_ref = self.selected_choice_id.name
            self.element_id.element_type = self.selected_choice_id.element_type
        return {'type': 'ir.actions.act_window_close'}


class AccessElementChoice(models.TransientModel):
    _name = 'access.element.choice'
    _description = 'UI Element Choice'

    wizard_id = fields.Many2one('access.element.wizard', ondelete='cascade')
    name = fields.Char(string='Technical Name')
    label = fields.Char(string='Label')
    element_type = fields.Selection([
        ('button', 'Button'),
        ('page', 'Notebook Page / Tab'),
        ('kanban_link', 'Kanban Link')
    ], string='Type')
    
    display_name = fields.Char(compute='_compute_display_name')

    @api.depends('name', 'label', 'element_type')
    def _compute_display_name(self):
        for rec in self:
            label_part = f"{rec.label} " if rec.label else ""
            type_part = f"[{rec.element_type.title()}]" if rec.element_type else ""
            rec.display_name = f"{label_part}({rec.name}) {type_part}"
