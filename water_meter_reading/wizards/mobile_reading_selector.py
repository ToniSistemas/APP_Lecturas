from odoo import _, api, fields, models
from odoo.exceptions import UserError


class WaterReadingMobileSelector(models.TransientModel):
    _name = 'water.reading.mobile.selector'
    _description = 'Seleccionar lectura móvil'

    period_id = fields.Many2one('water.period', string='Período', required=True, readonly=True)
    address_id = fields.Many2one('water.reading.mobile.address.option', readonly=True)
    street_id = fields.Many2one(
        'water.reading.mobile.street',
        string='Calle',
        ondelete='set null',
    )
    pueblo_id = fields.Many2one(
        'water.reading.mobile.pueblo',
        string='Pueblo',
        ondelete='set null',
    )
    pending_street = fields.Char(string='Calle + Ubicación')
    all_street = fields.Char(string='Calle + Ubicación')
    only_pending = fields.Boolean(string='Solo pendientes', default=True)
    available_meter_ids = fields.Many2many('water.meter', compute='_compute_counts')
    available_route_ids = fields.Many2many(
        'water.reading.mobile.route',
        compute='_compute_counts',
    )
    available_street_ids = fields.Many2many(
        'water.reading.mobile.street',
        compute='_compute_counts',
    )
    available_pueblo_ids = fields.Many2many(
        'water.reading.mobile.pueblo',
        compute='_compute_counts',
    )
    total_count = fields.Integer(compute='_compute_counts', string='Total contadores')
    read_count = fields.Integer(compute='_compute_counts', string='Contadores leídos')
    available_count = fields.Integer(compute='_compute_counts', string='Pendientes')
    route_id = fields.Many2one(
        'water.reading.mobile.route',
        string='Ruta',
        required=True,
        domain="[('period_id', '=', period_id), ('active', '=', True)]",
    )

    @api.model
    def _sync_streets(self, period_id):
        Street = self.env['water.reading.mobile.street'].sudo().with_context(active_test=False)
        Pueblo = self.env['water.reading.mobile.pueblo'].sudo().with_context(active_test=False)
        Route = self.env['water.reading.mobile.route'].sudo().with_context(active_test=False)
        period = self.env['water.period'].browse(period_id)
        meters = period.reading_ids.sudo().mapped('meter_id')
        meter_routes = {meter.name.strip() for meter in meters if meter.name and meter.name.strip()}
        current_routes = Route.search([('period_id', '=', period.id)])
        current_routes.write({'active': False})
        for route in meter_routes:
            record = current_routes.filtered(lambda item: item.name == route)[:1]
            meter = meters.filtered(lambda item: item.name.strip() == route)[:1]
            values = {
                'active': True,
                'route_order': int(route) if route.isdigit() else 0,
                'meter_number': meter.meter_number if meter else False,
                'owner_name': meter.owner_name if meter else False,
                'subscriber': meter.subscriber if meter else False,
                'street': meter.street if meter else False,
                'pueblo': meter.pueblo if meter else False,
                'location': meter.street_number if meter else False,
            }
            if record:
                record.write(values)
            else:
                Route.create(dict(values, name=route, period_id=period.id))
        meter_pueblos = {
            meter.pueblo.strip()
            for meter in meters
            if meter.pueblo and meter.pueblo.strip()
        }
        current_pueblos = Pueblo.search([('period_id', '=', period.id)])
        current_pueblos.write({'active': False})
        for pueblo in meter_pueblos:
            record = current_pueblos.filtered(lambda item: item.name == pueblo)[:1]
            if record:
                record.write({'active': True})
            else:
                Pueblo.create({'name': pueblo, 'period_id': period.id, 'active': True})
        meter_streets = {
            (meter.street or meter.address).strip()
            for meter in meters
            if (meter.street or meter.address) and (meter.street or meter.address).strip()
        }
        current_streets = Street.search([('period_id', '=', period.id)])
        current_streets.write({'active': False})
        for street in meter_streets:
            record = current_streets.filtered(lambda item: item.name == street)[:1]
            if record:
                record.write({'active': True})
            else:
                Street.create({'name': street, 'period_id': period.id, 'active': True})

    @api.model_create_multi
    def create(self, vals_list):
        period_id = vals_list[0].get('period_id') or self.env.context.get('default_period_id')
        if period_id:
            self._sync_streets(period_id)
        return super().create(vals_list)

    @api.onchange('only_pending')
    def _onchange_only_pending(self):
        self.street_id = False
        self.pueblo_id = False
        self.route_id = False
        self.pending_street = False
        self.all_street = False

    def _filtered_readings(self):
        self.ensure_one()
        readings = self.period_id.reading_ids.sudo()
        if self.route_id:
            selected_route = self.route_id.name.strip().casefold()
            readings = readings.filtered(
                lambda reading: (reading.meter_route or '').strip().casefold() == selected_route
            )
        if self.street_id:
            selected_street = self.street_id.name.strip().casefold()
            readings = readings.filtered(
                lambda reading: (reading.meter_id.street or reading.meter_id.address or '')
                .strip().casefold() == selected_street
            )
        if self.pueblo_id:
            selected_pueblo = self.pueblo_id.name.strip().casefold()
            readings = readings.filtered(
                lambda reading: (reading.meter_id.pueblo or '').strip().casefold() == selected_pueblo
            )
        if self.only_pending:
            readings = readings.filtered(lambda reading: reading.reading_current == 0)
        return readings

    @api.depends('period_id', 'street_id', 'pueblo_id', 'route_id', 'pending_street', 'all_street', 'only_pending')
    def _compute_counts(self):
        for wizard in self:
            all_readings = wizard.period_id.reading_ids.sudo()
            wizard.total_count = len(all_readings)
            wizard.read_count = len(all_readings.filtered(lambda reading: reading.reading_current != 0))
            readings = wizard._filtered_readings()
            wizard.available_meter_ids = readings.mapped('meter_id')
            wizard.available_count = len(wizard.available_meter_ids)
            route_names = set(readings.mapped('meter_route'))
            wizard.available_route_ids = self.env['water.reading.mobile.route'].search([
                ('period_id', '=', wizard.period_id.id),
                ('active', '=', True),
                ('name', 'in', list(route_names)),
            ])
            street_names = {
                (reading.meter_id.street or reading.meter_id.address).strip()
                for reading in readings
                if (reading.meter_id.street or reading.meter_id.address)
            }
            pueblo_names = {
                reading.meter_id.pueblo.strip()
                for reading in readings
                if reading.meter_id.pueblo and reading.meter_id.pueblo.strip()
            }
            wizard.available_street_ids = self.env['water.reading.mobile.street'].search([
                ('period_id', '=', wizard.period_id.id),
                ('active', '=', True),
                ('name', 'in', list(street_names)),
            ])
            wizard.available_pueblo_ids = self.env['water.reading.mobile.pueblo'].search([
                ('period_id', '=', wizard.period_id.id),
                ('active', '=', True),
                ('name', 'in', list(pueblo_names)),
            ])

    @api.onchange('street_id', 'pueblo_id', 'route_id', 'pending_street', 'all_street')
    def _onchange_street(self):
        self._compute_counts()

    @api.onchange('only_pending')
    def _onchange_pending_options(self):
        self._compute_counts()

    def action_open_reading(self):
        self.ensure_one()
        reading = self._filtered_readings()[:1]
        if not reading:
            raise UserError(_('La ruta seleccionada no tiene una lectura pendiente en este período.'))
        return reading._mobile_action(
            mobile_street=self.street_id.name if self.street_id else '',
            mobile_pueblo=self.pueblo_id.name if self.pueblo_id else '',
        )