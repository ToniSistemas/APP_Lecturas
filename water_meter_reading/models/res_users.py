from odoo import models, fields


class ResUsers(models.Model):
    _inherit = 'res.users'

    can_edit_readings = fields.Boolean(
        string='Puede modificar lectura anterior',
        default=False,
    )
