from odoo import _, api, fields, models
from odoo.exceptions import UserError


class WaterReadingMobileSelector(models.TransientModel):
    _name = 'water.reading.mobile.selector'
    _description = 'Seleccionar lectura móvil'

    period_id = fields.Many2one('water.period', string='Período', required=True, readonly=True)
    address_id = fields.Many2one('water.reading.mobile.address.option', readonly=True)
    pending_street = fields.Selection(selection='_selection_pending_streets', string='Calle + Nº')
    all_street = fields.Selection(selection='_selection_all_streets', string='Calle + Nº')
    only_pending = fields.Boolean(string='Solo pendientes', default=True)
    available_meter_ids = fields.Many2many('water.meter', compute='_compute_available_meter_ids')
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
    def _street_options(self, period_id, pending):
        meters = self.env['water.meter'].sudo().with_context(active_test=False).search([])
        addresses = {
            (
                (meter.street or meter.address).strip(),
                (meter.street_number or '').strip(),
            )
            for meter in meters
            if (meter.street or meter.address) and (meter.street or meter.address).strip()
        }
        addresses = sorted(addresses, key=lambda address: (address[0].casefold(), address[1].casefold()))
        return [
            (f'{street}|{number}', f'{street} {number}'.strip())
            for street, number in addresses
        ]

    @api.model
    def _selection_pending_streets(self):
        return self._street_options(False, True)

    @api.model
    def _selection_all_streets(self):
        return self._street_options(False, False)

    @api.onchange('only_pending')
    def _onchange_only_pending(self):
        self.pending_street = False
        self.all_street = False

    def _filtered_readings(self):
        self.ensure_one()
        readings = self.period_id.reading_ids.sudo()
        selected_filter = self.pending_street if self.only_pending else self.all_street
        if selected_filter:
            selected_street, selected_number = selected_filter.split('|', 1)
            selected_street = selected_street.strip().casefold()
            selected_number = selected_number.strip().casefold()
            readings = readings.filtered(
                lambda reading: (
                    (reading.meter_id.street or reading.meter_id.address or '').strip().casefold()
                    == selected_street
                    and (reading.meter_id.street_number or '').strip().casefold()
                    == selected_number
                )
            )
        if self.only_pending:
            readings = readings.filtered(lambda reading: reading.reading_current == 0)
        return readings

    @api.depends('period_id', 'pending_street', 'all_street', 'only_pending')
    def _compute_counts(self):
        for wizard in self:
            all_readings = wizard.period_id.reading_ids.sudo()
            wizard.total_count = len(all_readings)
            wizard.read_count = len(all_readings.filtered(lambda reading: reading.reading_current != 0))
            readings = wizard._filtered_readings()
            wizard.available_meter_ids = readings.mapped('meter_id')
            wizard.available_count = len(wizard.available_meter_ids)

    @api.onchange('pending_street', 'all_street')
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