from odoo import models, fields, api


class WaterReading(models.Model):
    _name = 'water.reading'
    _description = 'Meter Reading'
    _order = 'date desc'

    name = fields.Char(string='Referencia', readonly=True, copy=False)
    meter_id = fields.Many2one('water.meter', string='Contador', required=True, ondelete='cascade')
    meter_number = fields.Char(related='meter_id.meter_number', string='Contador Nº', store=True, readonly=True)
    meter_route = fields.Char(related='meter_id.name', string='Ruta', store=True, readonly=True)
    date = fields.Date(string='Fecha', required=True, default=fields.Date.context_today)
    reading_previous = fields.Integer(string='Lectura anterior')
    reading_current = fields.Integer(string='Lectura actual')
    difference = fields.Integer(string='Diferencia', compute='_compute_difference', store=True)
    observations = fields.Text(string='Observaciones')
    user_id = fields.Many2one('res.users', string='Capturado por', default=lambda self: self.env.user)
    period_id = fields.Many2one('water.period', string='Período', ondelete='set null', index=True)
    photo_ids = fields.One2many('water.reading.photo', 'reading_id', string='Fotografías')
    counter_photo = fields.Image(string='Foto del contador', max_width=1024, max_height=1024)
    allow_edit_previous = fields.Boolean(
        compute='_compute_allow_edit_previous',
        string='Puede editar lectura anterior',
    )

    @api.depends_context('uid')
    def _compute_allow_edit_previous(self):
        user = self.env.user.sudo()
        can_edit = user.can_edit_readings or user.has_group('water_meter_reading.group_water_supervisor')
        for rec in self:
            rec.allow_edit_previous = can_edit

    @api.depends('reading_current', 'reading_previous')
    def _compute_difference(self):
        for rec in self:
            rec.difference = rec.reading_current - rec.reading_previous

    @api.onchange('meter_id')
    def _onchange_meter_id(self):
        if self.meter_id:
            last = self.env['water.reading'].search([('meter_id', '=', self.meter_id.id)], order='date desc', limit=1)
            if last:
                self.reading_previous = last.reading_current

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('meter_id') and not vals.get('reading_previous'):
                last = self.env['water.reading'].search(
                    [('meter_id', '=', vals['meter_id'])], order='date desc', limit=1
                )
                if last:
                    vals['reading_previous'] = last.reading_current
            if not vals.get('name'):
                vals['name'] = self.env['ir.sequence'].next_by_code('water.reading') or '/'
        return super().create(vals_list)
