from odoo import models, fields, api, _
from odoo.exceptions import UserError


class WaterPeriod(models.Model):
    _name = 'water.period'
    _description = 'Período de lectura trimestral'
    _order = 'year desc, trimester desc'

    _sql_constraints = [
        ('unique_period', 'UNIQUE(trimester, year)',
         'Ya existe un período para ese trimestre y año.'),
    ]

    name = fields.Char(string='Período', compute='_compute_name', store=True)
    trimester = fields.Selection([
        ('1', '1er Trimestre'),
        ('2', '2º Trimestre'),
        ('3', '3er Trimestre'),
        ('4', '4º Trimestre'),
    ], string='Trimestre', required=True)
    year = fields.Integer(
        string='Año', required=True,
        default=lambda self: fields.Date.today().year,
    )
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('open', 'Abierto'),
        ('closed', 'Cerrado'),
    ], string='Estado', default='draft', readonly=True)
    reading_ids = fields.One2many('water.reading', 'period_id', string='Lecturas')
    reading_count = fields.Integer(compute='_compute_reading_count', string='Lecturas')

    @api.depends('trimester', 'year')
    def _compute_name(self):
        for rec in self:
            rec.name = f"{rec.trimester}T{rec.year}" if rec.trimester and rec.year else ''

    @api.depends('reading_ids')
    def _compute_reading_count(self):
        for rec in self:
            rec.reading_count = len(rec.reading_ids)

    def action_generate_readings(self):
        self.ensure_one()
        if self.state == 'closed':
            raise UserError(_('No se pueden generar lecturas en un período cerrado.'))
        all_meters = self.env['water.meter'].search([])
        existing_meters = self.reading_ids.mapped('meter_id')
        pending = all_meters - existing_meters
        if not pending:
            raise UserError(_('Todos los contadores ya tienen lectura en este período.'))
        Reading = self.env['water.reading']
        vals_list = []
        for meter in pending:
            last = Reading.search(
                [('meter_id', '=', meter.id)], order='date desc', limit=1
            )
            vals_list.append({
                'meter_id': meter.id,
                'period_id': self.id,
                'reading_previous': last.reading_current if last else 0,
                'date': fields.Date.context_today(self),
            })
        Reading.create(vals_list)
        if self.state == 'draft':
            self.state = 'open'

    def action_close(self):
        self.ensure_one()
        self.state = 'closed'

    def action_reopen(self):
        self.ensure_one()
        self.state = 'open'
