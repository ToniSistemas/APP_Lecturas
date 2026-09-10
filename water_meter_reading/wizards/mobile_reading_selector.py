from odoo import _, api, fields, models
from odoo.exceptions import UserError


class WaterReadingMobileSelector(models.TransientModel):
    _name = 'water.reading.mobile.selector'
    _description = 'Seleccionar lectura móvil'

    period_id = fields.Many2one('water.period', string='Período', required=True, readonly=True)
    address_id = fields.Many2one(
        'water.reading.mobile.address.option',
        string='Dirección',
        domain="[('id', 'in', available_address_ids)]",
    )
    available_address_ids = fields.Many2many('water.reading.mobile.address.option')
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
                address.strip()
                for address in readings.mapped('meter_id.address')
                if address and address.strip()
            }, key=str.casefold)
            address_records = Address.search([
                ('period_id', '=', wizard.period_id.id),
                ('name', 'in', addresses),
            ])
            existing_names = set(address_records.mapped('name'))
            address_records |= Address.create([
                {'period_id': wizard.period_id.id, 'name': address}
                for address in addresses if address not in existing_names
            ])
            address_records = address_records.filtered(lambda address: address.name in addresses)
            wizard.available_address_ids = [(6, 0, address_records.ids)]

    @api.depends('period_id', 'address_id', 'only_pending', 'available_address_ids')
    def _compute_counts(self):
        for wizard in self:
            readings = wizard.period_id.reading_ids
            wizard.total_count = len(readings)
            wizard.read_count = len(readings.filtered(lambda reading: reading.reading_current != 0))
            if wizard.address_id:
                readings = readings.filtered(
                    lambda reading: reading.meter_id.address == wizard.address_id.name
                )
            if wizard.only_pending:
                readings = readings.filtered(lambda reading: reading.reading_current == 0)
            wizard.available_meter_ids = readings.mapped('meter_id')
            wizard.available_count = len(wizard.available_meter_ids)

    @api.onchange('only_pending')
    def _onchange_only_pending(self):
        if self.id:
            self._refresh_addresses()
            self.address_id = False
        if self.meter_id and self.meter_id not in self.available_meter_ids:
            self.meter_id = False

    @api.onchange('address_id')
    def _onchange_address(self):
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