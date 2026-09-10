from odoo import fields, models


class WaterReadingMobileStreet(models.Model):
    _name = 'water.reading.mobile.street'
    _description = 'Calle del selector móvil'
    _rec_name = 'name'

    name = fields.Char(required=True)

    _unique_name = models.UniqueIndex(
        '(name)',
        'La calle ya existe.',
    )