from odoo import _, api, fields, models
from odoo.exceptions import UserError


class WaterReadingMobileSelector(models.TransientModel):
    _name = 'water.reading.mobile.selector'
    _description = 'Seleccionar lectura móvil'

    period_id = fields.Many2one('water.period', string='Período', required=True, readonly=True)
    route = fields.Selection(selection='_selection_addresses', string='Dirección')
    only_pending = fields.Boolean(string='Solo pendientes', default=True)
    available_meter_ids = fields.Many2many('water.meter', compute='_compute_available_meter_ids')
    available_count = fields.Integer(compute='_compute_available_meter_ids', string='Disponibles')
    meter_id = fields.Many2one(
        'water.meter',
        string='Contador',
        required=True,
        domain="[('id', 'in', available_meter_ids)]",
    )

    @api.model
    def _selection_addresses(self):
        meters = self.env['water.meter'].with_context(active_test=False).search([
            ('address', '!=', False),
        ])
        addresses = sorted(
            set(meters.mapped('address')),
            key=lambda address: address.casefold(),
        )
        return [(address, address) for address in addresses if address]

    @api.depends('period_id', 'route', 'only_pending')
    def _compute_available_meter_ids(self):
        for wizard in self:
            readings = wizard.period_id.reading_ids
            if wizard.route:
                readings = readings.filtered(lambda reading: reading.meter_id.address == wizard.route)
            if wizard.only_pending:
                readings = readings.filtered(lambda reading: reading.reading_current == 0)
            wizard.available_meter_ids = readings.mapped('meter_id')
            wizard.available_count = len(wizard.available_meter_ids)

    @api.onchange('route', 'only_pending')
    def _onchange_filters(self):
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