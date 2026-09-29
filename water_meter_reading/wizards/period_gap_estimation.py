from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class WaterPeriodGapEstimation(models.TransientModel):
    _name = 'water.period.gap.estimation'
    _description = 'Estimar período sin lecturas'

    source_period_id = fields.Many2one('water.period', string='Período con lectura real', required=True, readonly=True)
    target_period_id = fields.Many2one('water.period', string='Período a estimar', required=True, readonly=True)
    variation = fields.Selection([
        ('-5', '-5%'),
        ('0', '0%'),
        ('5', '+5%'),
    ], string='Variación', default='0', required=True)
    confirmed = fields.Boolean(string='Confirmo la estimación')
    summary = fields.Text(string='Resumen', readonly=True)
    line_ids = fields.One2many('water.period.gap.estimation.line', 'wizard_id', string='Vista previa')

    @staticmethod
    def _period_key(period):
        return (period.year, int(period.trimester))

    def _real_history(self, meter, before_period):
        readings = self.env['water.reading'].search([
            ('meter_id', '=', meter.id),
            ('reading_current', '>', 0),
        ]).filtered(lambda reading: reading.period_id and self._period_key(reading.period_id) <= self._period_key(before_period))
        readings = readings.sorted(key=lambda reading: (self._period_key(reading.period_id), reading.id))
        consumptions = {}
        previous = None
        for reading in readings:
            if previous and reading.reading_current >= previous.reading_current:
                trimester = int(reading.period_id.trimester)
                consumptions.setdefault(trimester, []).append(reading.reading_current - previous.reading_current)
            previous = reading
        return consumptions

    def action_prepare(self):
        self.ensure_one()
        current = self.source_period_id
        target = current._get_previous_period()
        if not target:
            raise UserError(_('No existe un período anterior para estimar.'))
        if target.state == 'closed':
            raise UserError(_('No se puede modificar un período cerrado.'))
        current_readings = {
            reading.meter_id.id: reading
            for reading in current.reading_ids
            if reading.reading_current > 0
        }
        target_readings = {
            reading.meter_id.id: reading
            for reading in target.reading_ids
            if reading.reading_current == 0
        }
        if not target_readings:
            raise UserError(_('El período anterior no tiene lecturas pendientes de estimar.'))
        variation = int(self.variation)
        lines = []
        estimated = unavailable = 0
        for meter_id, target_reading in target_readings.items():
            current_reading = current_readings.get(meter_id)
            meter = target_reading.meter_id
            before = self.env['water.reading'].search([
                ('meter_id', '=', meter_id),
                ('period_id', '!=', target.id),
                ('reading_current', '>', 0),
            ]).filtered(lambda reading: reading.period_id and self._period_key(reading.period_id) < self._period_key(target)).sorted(
                key=lambda reading: (self._period_key(reading.period_id), reading.id), reverse=True
            )[:1]
            status = 'unavailable'
            message = _('Sin lectura real anterior o posterior suficiente.')
            estimated_current = 0
            share = 0.0
            if current_reading and before:
                total = current_reading.reading_current - before.reading_current
                history = self._real_history(meter, before.period_id)
                target_consumptions = history.get(int(target.trimester), [])
                source_consumptions = history.get(int(current.trimester), [])
                if total > 0 and target_consumptions and source_consumptions:
                    base_share = sum(target_consumptions) / (sum(target_consumptions) + sum(source_consumptions))
                    share = max(0.05, min(0.95, base_share * (1 + variation / 100)))
                    estimated_current = before.reading_current + round(total * share)
                    status = 'ready'
                    message = _('Se estimará con una proporción histórica del %.1f%%.') % (share * 100)
                    estimated += 1
                else:
                    message = _('No hay consumo histórico válido para calcular la proporción.')
                    unavailable += 1
            else:
                unavailable += 1
            lines.append({
                'reading_id': target_reading.id,
                'meter_number': meter.meter_number,
                'subscriber': meter.subscriber,
                'before_reading': before.reading_current if before else 0,
                'source_reading': current_reading.reading_current if current_reading else 0,
                'estimated_reading': estimated_current,
                'share': share,
                'status': status,
                'message': message,
            })
        self.line_ids = [(5, 0, 0)] + [(0, 0, values) for values in lines]
        self.summary = _(
            'Preparadas: %(estimated)s | Sin datos suficientes: %(unavailable)s. '
            'No se ha modificado ninguna lectura.'
        ) % {'estimated': estimated, 'unavailable': unavailable}
        return {
            'type': 'ir.actions.act_window',
            'name': _('Vista previa de estimación'),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_confirm(self):
        self.ensure_one()
        if self.source_period_id.state == 'closed' or self.target_period_id.state == 'closed':
            raise UserError(_('No se puede estimar sobre un período cerrado.'))
        if not self.confirmed:
            raise ValidationError(_('Marca la confirmación antes de modificar las lecturas.'))
        readings = self.env['water.reading']
        for line in self.line_ids.filtered(lambda item: item.status == 'ready'):
            reading = line.reading_id
            reading.with_context(skip_estimation_reset=True).write({
                'reading_previous': line.before_reading,
                'reading_current': line.estimated_reading,
                'estimated_reading': True,
                'estimated_note': _(
                    'Estimación entre %(before)s y %(source)s; proporción aplicada: %(share).1f%%.'
                ) % {
                    'before': self.target_period_id._get_previous_period().name if self.target_period_id._get_previous_period() else '-',
                    'source': self.source_period_id.name,
                    'share': line.share * 100,
                },
                'estimated_by': self.env.user.id,
                'estimated_at': fields.Datetime.now(),
            })
            readings |= reading
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Estimación completada'),
                'message': _('%s lecturas estimadas.') % len(readings),
                'type': 'success',
                'sticky': False,
            },
        }


class WaterPeriodGapEstimationLine(models.TransientModel):
    _name = 'water.period.gap.estimation.line'
    _description = 'Línea de estimación de período'

    wizard_id = fields.Many2one('water.period.gap.estimation', required=True, ondelete='cascade')
    reading_id = fields.Many2one('water.reading', string='Lectura', readonly=True)
    meter_number = fields.Char(string='Contador', readonly=True)
    subscriber = fields.Char(string='Abonado', readonly=True)
    before_reading = fields.Integer(string='Lectura límite', readonly=True)
    source_reading = fields.Integer(string='Lectura real posterior', readonly=True)
    estimated_reading = fields.Integer(string='Lectura estimada', readonly=True)
    share = fields.Float(string='Proporción', readonly=True)
    status = fields.Selection([
        ('ready', 'Lista'),
        ('unavailable', 'Sin datos suficientes'),
    ], string='Estado', readonly=True)
    message = fields.Char(string='Detalle', readonly=True)
