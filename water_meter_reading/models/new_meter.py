from odoo import fields, models


class WaterNewMeter(models.Model):
    _name = 'water.new.meter'
    _description = 'Contador nuevo pendiente de alta'
    _order = 'period_id desc, id desc'
    _rec_name = 'meter_number'

    period_id = fields.Many2one(
        'water.period',
        string='Período',
        required=True,
        ondelete='cascade',
        index=True,
    )
    meter_number = fields.Char(string='Contador', required=True)
    route = fields.Char(string='Ruta')
    pueblo = fields.Char(string='Pueblo')
    street = fields.Char(string='Calle')
    street_number = fields.Char(string='Ubicación')
    address = fields.Char(string='Dirección')
    owner_name = fields.Char(string='Nombre')
    subscriber = fields.Char(string='Abonado')
    cadastral_ref = fields.Char(string='Referencia catastral')
    counter_photo = fields.Image(
        string='Foto del contador',
        max_width=1024,
        max_height=1024,
    )
    meter_type = fields.Selection([
        ('dom', 'DOM - Doméstico'),
        ('asim', 'ASIM - Asimilado'),
        ('ndom', 'NDOM - No doméstico'),
        ('esp', 'ESP - Especial'),
    ], string='Tipo de contador')
    observations = fields.Text(string='Observaciones')
    state = fields.Selection([
        ('pending', 'Pendiente de alta'),
        ('registered', 'Dado de alta'),
        ('rejected', 'Descartado'),
    ], string='Estado', default='pending', required=True)
    user_id = fields.Many2one(
        'res.users',
        string='Registrado por',
        default=lambda self: self.env.user,
        readonly=True,
    )
    date = fields.Datetime(string='Fecha', default=fields.Datetime.now, readonly=True)
