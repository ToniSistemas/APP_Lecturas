from odoo import _, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


class WaterMeterGtbUpdate(models.TransientModel):
    _name = 'water.meter.gtb.update'
    _description = 'Actualizar lecturas desde GTB'

    period_id = fields.Many2one('water.period', string='Período', required=True, readonly=True)
    line_ids = fields.One2many('water.meter.gtb.update.line', 'wizard_id', string='Vista previa')
    summary = fields.Text(string='Resumen', readonly=True)
    confirmed = fields.Boolean(string='Confirmo la actualización en producción')

    @staticmethod
    def _key(subscriber, meter_number):
        return (str(subscriber or '').strip(), str(meter_number or '').strip())

    def action_prepare(self, rows):
        self.ensure_one()
        self._check_gtb_access()
        if self.period_id.state == 'closed':
            raise UserError(_('No se puede actualizar un período cerrado.'))
        readings = {
            self._key(reading.meter_id.subscriber, reading.meter_id.meter_number): reading
            for reading in self.period_id.reading_ids
        }
        route_owners = {
            meter.name: meter
            for meter in self.env['water.meter'].search([])
            if meter.name
        }
        line_values = []
        matched = not_found = invalid = 0
        for row in rows:
            key = self._key(row.get('abonado'), row.get('contador'))
            reading = readings.get(key)
            raw_current = row.get('lectura_actual')
            raw_consumption = row.get('consumo')
            try:
                new_current = int(raw_current) if raw_current not in (None, '') else None
                gtb_consumption = int(raw_consumption) if raw_consumption not in (None, '') else None
            except (TypeError, ValueError):
                new_current = gtb_consumption = None
            if not reading:
                status = 'not_found'
                status_message = _('No existe una lectura con ese abonado y contador.')
                not_found += 1
            elif new_current is None or gtb_consumption is None:
                status = 'invalid'
                status_message = _('Lectura actual o consumo no numérico.')
                invalid += 1
            elif row.get('ruta') and route_owners.get(str(row['ruta']).strip()) not in (None, reading.meter_id):
                status = 'invalid'
                status_message = _('La ruta GTB ya pertenece a otro contador.')
                invalid += 1
            else:
                status = 'matched'
                status_message = _('Se actualizará al confirmar.')
                matched += 1
            line_values.append({
                'reading_id': reading.id if reading else False,
                'subscriber': key[0],
                'meter_number': key[1],
                'old_route': reading.meter_id.name if reading else False,
                'new_route': str(row.get('ruta') or '').strip(),
                'old_current': reading.reading_current if reading else 0,
                'new_current': new_current or 0,
                'old_consumption': reading.difference if reading else 0,
                'gtb_consumption': gtb_consumption or 0,
                'status': status,
                'status_message': status_message,
            })
        self.line_ids = [(5, 0, 0)] + [(0, 0, values) for values in line_values]
        self.summary = _(
            'Coincidentes: %(matched)s | No encontradas: %(not_found)s | Inválidas: %(invalid)s. '
            'No se ha modificado ninguna lectura.'
        ) % {'matched': matched, 'not_found': not_found, 'invalid': invalid}
        return {
            'type': 'ir.actions.act_window',
            'name': _('Vista previa actualización GTB'),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _check_gtb_access(self):
        if not (
            self.env.user.has_group('base.group_system')
            or self.env.user.has_group('water_meter_reading.group_water_supervisor')
        ):
            raise AccessError(_('Solo administradores y supervisores pueden actualizar datos GTB.'))

    def action_confirm(self):
        self.ensure_one()
        self._check_gtb_access()
        if self.period_id.state == 'closed':
            raise UserError(_('No se puede actualizar un período cerrado.'))
        if not self.confirmed:
            raise ValidationError(_('Revisa la vista previa y confirma expresamente la actualización.'))
        lines = self.line_ids.filtered(lambda line: line.status == 'matched')
        if not lines:
            raise UserError(_('No hay lecturas coincidentes para actualizar.'))
        for line in lines:
            values = {
                'reading_current': line.new_current,
            }
            if line.new_route and line.new_route != line.reading_id.meter_id.name:
                line.reading_id.meter_id.write({'name': line.new_route})
            line.reading_id.with_context(skip_meter_replacement=True).write(values)
        self.confirmed = False
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Actualización GTB completada'),
                'message': _('%s lecturas actualizadas.') % len(lines),
                'type': 'success',
                'sticky': False,
            },
        }


class WaterMeterGtbUpdateLine(models.TransientModel):
    _name = 'water.meter.gtb.update.line'
    _description = 'Vista previa de actualización GTB'

    wizard_id = fields.Many2one('water.meter.gtb.update', required=True, ondelete='cascade')
    reading_id = fields.Many2one('water.reading', string='Lectura', readonly=True)
    subscriber = fields.Char(string='Abonado', readonly=True)
    meter_number = fields.Char(string='Contador', readonly=True)
    old_route = fields.Char(string='Ruta actual', readonly=True)
    new_route = fields.Char(string='Ruta GTB', readonly=True)
    old_current = fields.Integer(string='Lectura actual', readonly=True)
    new_current = fields.Integer(string='Lectura GTB', readonly=True)
    old_consumption = fields.Integer(string='Consumo Odoo', readonly=True)
    gtb_consumption = fields.Integer(string='Consumo GTB', readonly=True)
    status = fields.Selection([
        ('matched', 'Coincide'),
        ('not_found', 'No encontrada'),
        ('invalid', 'Dato inválido'),
    ], string='Resultado', readonly=True)
    status_message = fields.Char(string='Detalle', readonly=True)
