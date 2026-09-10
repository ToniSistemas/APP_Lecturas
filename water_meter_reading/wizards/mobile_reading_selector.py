from odoo import _, api, fields, models
from odoo.exceptions import UserError


class WaterReadingMobileSelector(models.TransientModel):
    _name = 'water.reading.mobile.selector'
    _description = 'Seleccionar lectura móvil'

    period_id = fields.Many2one('water.period', string='Período', required=True, readonly=True)
    route = fields.Selection(selection='_selection_addresses', string='Dirección')
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
    def _selection_addresses(self):
        period_id = (
            self.env.context.get('default_period_id')
            or self.env.context.get('active_id')
        )
        if period_id:
            period = self.env['water.period'].browse(period_id)
            meters = period.reading_ids.sudo().mapped('meter_id')
        else:
            meters = self.env['water.meter'].sudo().with_context(active_test=False).search([])
        addresses = {
            address.strip()
            for address in meters.mapped('address')
            if address and address.strip()
        }
        addresses = sorted(
            addresses,
            key=lambda address: address.casefold(),
        )
        return [(address, address) for address in addresses if address]

    @api.depends('period_id', 'route', 'only_pending')
    def _compute_counts(self):
        for wizard in self:
            readings = wizard.period_id.reading_ids
            wizard.total_count = len(readings)
            wizard.read_count = len(readings.filtered(lambda reading: reading.reading_current != 0))
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