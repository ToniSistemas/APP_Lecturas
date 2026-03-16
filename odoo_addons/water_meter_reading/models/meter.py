from odoo import models, fields


class WaterMeter(models.Model):
    _name = 'water.meter'
    _description = 'Water Meter'

    name = fields.Char(string='Ruta', required=True)
    meter_number = fields.Char(string='Contador')
    address = fields.Char(string='Dirección')
    zip = fields.Char(string='C.P.')
    municipality = fields.Char(string='Municipio')
    owner_name = fields.Char(string='Nombre')

    reading_ids = fields.One2many('water.reading', 'meter_id', string='Lecturas')
