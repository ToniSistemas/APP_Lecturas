from odoo import fields, models


class WaterReadingMobileAddressOption(models.Model):
    _name = 'water.reading.mobile.address.option'
    _description = 'Dirección del selector móvil'
    _rec_name = 'name'

    name = fields.Char(required=True)
    period_id = fields.Many2one('water.period', required=True, ondelete='cascade', index=True)

    _unique_period_address = models.UniqueIndex(
        '(period_id, name)',
        'La dirección ya existe en este período.',
    )