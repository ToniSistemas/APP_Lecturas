from odoo import fields, models


class WaterReadingMobileStreet(models.Model):
    _name = 'water.reading.mobile.street'
    _description = 'Calle del selector móvil'
    _rec_name = 'name'

    name = fields.Char(required=True)
    period_id = fields.Many2one('water.period', index=True, ondelete='cascade')

    _unique_period_name = models.UniqueIndex(
        '(period_id, name)',
        'La calle ya existe en este período.',
    )