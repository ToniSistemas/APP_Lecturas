from odoo import _, api, fields, models
from odoo.exceptions import UserError


class WaterReadingMobileSelector(models.TransientModel):
    _name = 'water.reading.mobile.selector'
    _description = 'Seleccionar lectura móvil'

    period_id = fields.Many2one('water.period', string='Período', required=True, readonly=True)
    address_id = fields.Many2one(
        'water.reading.mobile.address.option',
        string='Calle + Nº',
        domain="[('id', 'in', available_address_ids)]",
    )
    available_address_ids = fields.Many2many(
        'water.reading.mobile.address.option',
        relation='water_mobile_addr_rel',
        column1='selector_id',
        column2='address_id',
    )
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

    @api.model_create_multi
    def create(self, vals_list):
        wizards = super().create(vals_list)
        wizards._refresh_addresses()
        return wizards

    def _refresh_addresses(self):
        Address = self.env['water.reading.mobile.address.option'].sudo()
        for wizard in self:
            readings = wizard.period_id.reading_ids.sudo()
            if wizard.only_pending:
                readings = readings.filtered(lambda reading: reading.reading_current == 0)
            addresses = sorted({
                (
                    (meter.street or meter.address).strip(),
                    (meter.street_number or '').strip(),
                )
                for meter in readings.mapped('meter_id')
                if (meter.street or meter.address) and (meter.street or meter.address).strip()
            }, key=lambda address: (address[0].casefold(), address[1].casefold()))
            address_records = Address.search([
                ('period_id', '=', wizard.period_id.id),
                ('street', 'in', [address[0] for address in addresses]),
            ])
            existing_keys = {
                (address.street, address.street_number or '')
                for address in address_records
            }
            address_records |= Address.create([
                {
                    'period_id': wizard.period_id.id,
                    'street': street,
                    'street_number': street_number,
                    'name': f'{street} {street_number}'.strip(),
                }
                for street, street_number in addresses
                if (street, street_number) not in existing_keys
            ])
            address_records = address_records.filtered(
                lambda address: (address.street, address.street_number or '') in addresses
            )
            wizard.available_address_ids = [(6, 0, address_records.ids)]

    def _filtered_readings(self):
        self.ensure_one()
        readings = self.period_id.reading_ids.sudo()
        if self.address_id:
            selected_street = self.address_id.street.strip().casefold()
            selected_number = (self.address_id.street_number or '').strip().casefold()
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

    @api.depends('period_id', 'address_id', 'only_pending', 'available_address_ids')
    def _compute_counts(self):
        for wizard in self:
            all_readings = wizard.period_id.reading_ids.sudo()
            wizard.total_count = len(all_readings)
            wizard.read_count = len(all_readings.filtered(lambda reading: reading.reading_current != 0))
            readings = wizard._filtered_readings()
            wizard.available_meter_ids = readings.mapped('meter_id')
            wizard.available_count = len(wizard.available_meter_ids)

    @api.onchange('only_pending')
    def _onchange_only_pending(self):
        if self.id:
            self._refresh_addresses()
            self.address_id = False
            self._compute_counts()
        if self.meter_id and self.meter_id not in self.available_meter_ids:
            self.meter_id = False

    @api.onchange('address_id')
    def _onchange_address(self):
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