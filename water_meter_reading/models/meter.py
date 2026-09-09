from odoo import models, fields, api


class WaterMeter(models.Model):
    _name = 'water.meter'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Contador de agua'
    _rec_name = 'meter_number'

    _sql_constraints = [
        ('unique_meter_number', 'UNIQUE(meter_number)', 'El número de contador ya existe. Debe ser único.'),
        ('unique_ruta', 'UNIQUE(name)', 'La ruta ya existe. Debe ser única.'),
    ]

    name = fields.Char(string='Ruta', required=True, tracking=True)
    meter_number = fields.Char(string='Contador', tracking=True)
    active = fields.Boolean(string='Activo', default=True, tracking=True)
    address = fields.Char(string='Dirección', tracking=True)
    zip = fields.Char(string='C.P.', tracking=True)
    municipality = fields.Char(string='Municipio', tracking=True)
    owner_name = fields.Char(string='Nombre', tracking=True)
    subscriber = fields.Char(string='Abonado', tracking=True)
    cadastral_ref = fields.Char(string='Referencia catastral', tracking=True)
    new_meter = fields.Boolean(string='Contador nuevo', default=False, tracking=True)
    meter_type = fields.Selection([
        ('dom', 'DOM - Doméstico'),
        ('asim', 'ASIM - Asimilado'),
        ('ndom', 'NDOM - No doméstico'),
        ('esp', 'ESP - Especial'),
    ], string='Tipo de contador', tracking=True)
    reversed_meter = fields.Boolean(string='Contador al revés', default=False, tracking=True)
    meter_max_value = fields.Integer(
        string='Valor máximo del contador',
        default=9999,
        tracking=True,
        help='Valor en el que el contador da la vuelta (ej: 9999, 99999). '
             'Solo se usa si «Contador al revés» está activo.',
    )

    reading_ids = fields.One2many('water.reading', 'meter_id', string='Lecturas')

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if self.env.context.get('skip_initial_reading'):
            return records
        latest_period = self.env['water.period'].search(
            [('state', 'in', ('draft', 'open'))],
            order='year desc, trimester desc',
            limit=1,
        )
        if latest_period:
            Reading = self.env['water.reading']
            for meter in records.filtered('active'):
                last = Reading.search(
                    [('meter_id', '=', meter.id)], order='date desc, create_date desc', limit=1
                )
                Reading.create({
                    'meter_id': meter.id,
                    'period_id': latest_period.id,
                    'reading_previous': last.reading_current if last else 0,
                    'date': fields.Date.context_today(self),
                })
        return records

