from odoo import fields , models


class ProjectTask(models.Model):
    _inherit = 'project.task'

    x_studio_modules = fields.Many2many(
    'project.task',
    'project_task_pro_studio_modules_rel',  # relation table name
    'task_id',                              # column for this record
    'module_task_id',                       # column for the related record
    string="Modules")
