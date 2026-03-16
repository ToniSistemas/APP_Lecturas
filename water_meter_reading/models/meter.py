from odoo import models, fields


class WaterMeter(models.Model):
    _name = 'water.meter'
    _description = 'Contador de agua'
    _rec_name = 'meter_number'

    _sql_constraints = [
        ('unique_meter_number', 'UNIQUE(meter_number)', 'El número de contador ya existe. Debe ser único.'),
        ('unique_ruta', 'UNIQUE(name)', 'La ruta ya existe. Debe ser única.'),
    ]

    name = fields.Char(string='Ruta', required=True)
    meter_number = fields.Char(string='Contador', required=True)
    address = fields.Char(string='Dirección')
    zip = fields.Char(string='C.P.')
    municipality = fields.Char(string='Municipio')
    owner_name = fields.Char(string='Nombre')

    reading_ids = fields.One2many('water.reading', 'meter_id', string='Lecturas')

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = (
                f"{rec.meter_number} – {rec.name}"
                if rec.meter_number and rec.name
                else (rec.meter_number or rec.name or '')
            )
