from odoo import fields, models


class WaterReadingMobilePueblo(models.Model):
    _name = 'water.reading.mobile.pueblo'
    _description = 'Pueblo del selector móvil'
    _rec_name = 'name'

    name = fields.Char(required=True)
    period_id = fields.Many2one('water.period', index=True, ondelete='cascade')
    active = fields.Boolean(default=True)

    _unique_period_name = models.UniqueIndex(
        '(period_id, name)',
        'El pueblo ya existe en este período.',
    )
