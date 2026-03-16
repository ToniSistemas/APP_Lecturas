from odoo import models, fields


class WaterReadingPhoto(models.Model):
    _name = 'water.reading.photo'
    _description = 'Reading Photo'

    reading_id = fields.Many2one('water.reading', string='Lectura', required=True, ondelete='cascade')
    image = fields.Binary(string='Imagen')
    image_name = fields.Char(string='Nombre archivo')
    timestamp = fields.Datetime(string='Timestamp', default=fields.Datetime.now)
