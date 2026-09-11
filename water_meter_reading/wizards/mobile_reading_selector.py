from odoo import _, api, fields, models
from odoo.exceptions import UserError


class WaterReadingMobileSelector(models.TransientModel):
    _name = 'water.reading.mobile.selector'
    _description = 'Seleccionar lectura móvil'

    period_id = fields.Many2one('water.period', string='Período', required=True, readonly=True)
    address_id = fields.Many2one('water.reading.mobile.address.option', readonly=True)
    street_id = fields.Many2one('water.reading.mobile.street', string='Calle')
    pending_street = fields.Char(string='Calle + Ubicación')
    all_street = fields.Char(string='Calle + Ubicación')
    only_pending = fields.Boolean(string='Solo pendientes', default=True)
    available_meter_ids = fields.Many2many('water.meter', compute='_compute_counts')
    total_count = fields.Integer(compute='_compute_counts', string='Total contadores')
    read_count = fields.Integer(compute='_compute_counts', string='Contadores leídos')
    available_count = fields.Integer(compute='_compute_counts', string='Pendientes')
    meter_id = fields.Many2one(
        'water.meter',
        string='Contador',
        required=True,
        domain="[('id', 'in', available_meter_ids)]",
    )

    @api.model
    def _sync_streets(self, period_id):
        Street = self.env['water.reading.mobile.street'].sudo()
        period = self.env['water.period'].browse(period_id)
        Street.search([('period_id', '=', period.id)]).unlink()
        meters = period.reading_ids.sudo().mapped('meter_id')
        meter_streets = {
            (meter.street or meter.address).strip()
            for meter in meters
            if (meter.street or meter.address) and (meter.street or meter.address).strip()
        }
        Street.create([
            {'name': street, 'period_id': period.id}
            for street in meter_streets
        ])

    @api.model_create_multi
    def create(self, vals_list):
        period_id = vals_list[0].get('period_id') or self.env.context.get('default_period_id')
        if period_id:
            self._sync_streets(period_id)
        return super().create(vals_list)

    @api.onchange('only_pending')
    def _onchange_only_pending(self):
        self.street_id = False
        self.pending_street = False
        self.all_street = False

    def _filtered_readings(self):
        self.ensure_one()
        readings = self.period_id.reading_ids.sudo()
        if self.street_id:
            selected_street = self.street_id.name.strip().casefold()
            readings = readings.filtered(
                lambda reading: (reading.meter_id.street or reading.meter_id.address or '')
                .strip().casefold() == selected_street
            )
        if self.only_pending:
            readings = readings.filtered(lambda reading: reading.reading_current == 0)
        return readings

    @api.depends('period_id', 'street_id', 'pending_street', 'all_street', 'only_pending')
    def _compute_counts(self):
        for wizard in self:
            all_readings = wizard.period_id.reading_ids.sudo()
            wizard.total_count = len(all_readings)
            wizard.read_count = len(all_readings.filtered(lambda reading: reading.reading_current != 0))
            readings = wizard._filtered_readings()
            wizard.available_meter_ids = readings.mapped('meter_id')
            wizard.available_count = len(wizard.available_meter_ids)

    @api.onchange('street_id', 'pending_street', 'all_street')
    def _onchange_street(self):
        self._compute_counts()
        if self.meter_id and self.meter_id not in self.available_meter_ids:
            self.meter_id = False

    def action_open_reading(self):
        self.ensure_one()
        reading = self.env['water.reading'].search([
            ('period_id', '=', self.period_id.id),
            ('meter_id', '=', self.meter_id.id),
        ], limit=1)
        if not reading:
            raise UserError(_('El contador seleccionado no pertenece a este período.'))
        return reading._mobile_action()