from odoo import models, fields, api, _
from odoo.exceptions import UserError, AccessError


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

    def _get_previous_period(self):
        """Devuelve el período inmediatamente anterior a este, o False si no existe."""
        t = int(self.trimester)
        if t == 1:
            prev_t, prev_y = '4', self.year - 1
        else:
            prev_t, prev_y = str(t - 1), self.year
        return self.search([('trimester', '=', prev_t), ('year', '=', prev_y)], limit=1)

    def action_generate_readings(self):
        self.ensure_one()
        if self.state == 'closed':
            raise UserError(_('No se pueden generar lecturas en un período cerrado.'))
        all_meters = self.env['water.meter'].search([('active', '=', True)])
        existing_meters = self.reading_ids.mapped('meter_id')
        pending = all_meters - existing_meters
        if not pending:
            raise UserError(_('Todos los contadores ya tienen lectura en este período.'))

        prev_period = self._get_previous_period()
        Reading = self.env['water.reading']

        # Pre-fetch previous period readings indexed by meter_id for performance
        prev_by_meter = {}
        if prev_period:
            for r in Reading.search([('period_id', '=', prev_period.id)]):
                prev_by_meter[r.meter_id.id] = r.reading_current

        vals_list = []
        for meter in pending:
            if meter.id in prev_by_meter:
                prev_value = prev_by_meter[meter.id]
            else:
                # Fallback: no previous period reading, take any last reading
                last = Reading.search(
                    [('meter_id', '=', meter.id),
                     ('period_id', '!=', self.id)],
                    order='date desc, create_date desc', limit=1
                )
                prev_value = last.reading_current if last else 0
            vals_list.append({
                'meter_id': meter.id,
                'period_id': self.id,
                'reading_previous': prev_value,
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

    def unlink(self):
        if not self.env.user.has_group('water_meter_reading.group_water_supervisor'):
            raise AccessError(_('Solo los supervisores pueden eliminar períodos.'))
        return super().unlink()

    def action_view_readings_search(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Lecturas \u2013 {self.name}',
            'res_model': 'water.reading',
            'view_mode': 'list,form',
            'domain': [('period_id', '=', self.id)],
            'context': {'default_period_id': self.id},
        }
