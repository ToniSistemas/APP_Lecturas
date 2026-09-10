from odoo import fields, models


class WaterReadingMobileAddressOption(models.Model):
    _name = 'water.reading.mobile.address.option'
    _description = 'Dirección del selector móvil'
    _rec_name = 'name'

    name = fields.Char(required=True)
    street = fields.Char(string='Calle', required=True)
    street_number = fields.Char(string='Nº')
    period_id = fields.Many2one('water.period', required=True, ondelete='cascade', index=True)

    _unique_period_address = models.UniqueIndex(
        '(period_id, street, street_number)',
        'La calle y número ya existen en este período.',
    )