from odoo import fields, models


class WaterReadingMobileAddress(models.TransientModel):
    _name = 'water.reading.mobile.address'
    _description = 'Dirección del selector móvil'

    name = fields.Char(required=True)
    selector_id = fields.Many2one(
        'water.reading.mobile.selector',
        required=True,
        ondelete='cascade',
    )