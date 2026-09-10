from odoo import fields, models


class WaterReadingMobileAddressOption(models.Model):
    _name = 'water.reading.mobile.address.option'
    _description = 'Dirección del selector móvil'
    _rec_name = 'name'

    name = fields.Char(required=True)
    period_id = fields.Many2one('water.period', required=True, ondelete='cascade', index=True)

    _sql_constraints = [
        ('unique_period_address', 'UNIQUE(period_id, name)', 'La dirección ya existe en este período.'),
    ]