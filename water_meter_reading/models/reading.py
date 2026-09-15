from odoo import _, models, fields, api
from odoo.exceptions import ValidationError
from markupsafe import escape


class WaterReading(models.Model):
    _name = 'water.reading'
    _description = 'Meter Reading'
    _order = 'date desc'

    name = fields.Char(string='Referencia', readonly=True, copy=False)
    meter_id = fields.Many2one('water.meter', string='Contador', required=True, ondelete='cascade')
    meter_number = fields.Char(string='Contador Nº', readonly=True)
    meter_route = fields.Char(related='meter_id.name', string='Ruta', store=True, readonly=True)
    meter_owner_name = fields.Char(related='meter_id.owner_name', string='Nombre', store=True, readonly=True)
    meter_route_link = fields.Html(compute='_compute_meter_links', string='Ruta', sanitize=True)
    meter_owner_link = fields.Html(compute='_compute_meter_links', string='Nombre', sanitize=True)
    meter_subscriber = fields.Char(related='meter_id.subscriber', string='Abonado', readonly=True)
    meter_address = fields.Char(related='meter_id.address', string='Dirección', readonly=True)
    meter_street = fields.Char(related='meter_id.street', string='Calle', readonly=True)
    meter_street_number = fields.Char(related='meter_id.street_number', string='Ubicación', readonly=True)
    meter_zip = fields.Char(related='meter_id.zip', string='C.P.', store=True, readonly=True)
    meter_municipality = fields.Char(related='meter_id.municipality', string='Municipio', store=True, readonly=True)
    new_meter = fields.Boolean(string='Contador nuevo', default=False)
    previous_meter_number = fields.Char(string='Contador anterior', readonly=True)
    new_meter_number = fields.Char(string='Nuevo contador')
    meter_reversed = fields.Boolean(
        string='Contador dio la vuelta',
        default=False,
        help='Márcalo solo en el período en el que el contador pasa por cero.',
    )
    meter_max_value = fields.Integer(
        string='Valor máximo',
        default=9999,
        help='Último valor antes de volver a cero. Por ejemplo, 999 para pasar de 980 a 10.',
    )
    meter_closed = fields.Boolean(string='Cerrado', default=False)
    meter_missing = fields.Boolean(string='Sin contador', default=False)
    meter_broken = fields.Boolean(string='Roto', default=False)
    date = fields.Date(string='Fecha', required=True, default=fields.Date.context_today)
    reading_previous = fields.Integer(string='Lectura anterior')
    reading_current = fields.Integer(string='Lectura actual')
    difference = fields.Integer(string='Diferencia', compute='_compute_difference', store=True)
    estimated_reading = fields.Boolean(string='Lectura estimada', default=False, index=True)
    estimated_note = fields.Text(string='Detalle de estimación', readonly=True)
    estimated_by = fields.Many2one('res.users', string='Estimada por', readonly=True)
    estimated_at = fields.Datetime(string='Fecha de estimación', readonly=True)
    observations = fields.Text(string='Observaciones')
    user_id = fields.Many2one('res.users', string='Capturado por', default=lambda self: self.env.user)
    period_id = fields.Many2one('water.period', string='Período', ondelete='set null', index=True)
    photo_ids = fields.One2many('water.reading.photo', 'reading_id', string='Fotografías')
    counter_photo = fields.Image(string='Foto del contador', max_width=1024, max_height=1024)
    allow_edit_previous = fields.Boolean(
        compute='_compute_allow_edit_previous',
        string='Puede editar lectura anterior',
    )
    mobile_progress = fields.Char(compute='_compute_mobile_progress', string='Progreso')
    anomaly_severity = fields.Selection([
        ('none', 'Sin anomalía'),
        ('medium', 'Media'),
        ('high', 'Alta'),
        ('critical', 'Crítica'),
    ], string='Gravedad', default='none', readonly=True, index=True)
    anomaly_reason = fields.Text(string='Motivo de revisión', readonly=True)
    anomaly_unchanged = fields.Boolean(string='Lectura sin cambios', readonly=True, index=True)
    review_status = fields.Selection([
        ('pending', 'Pendiente'),
        ('reviewed', 'Revisada'),
        ('corrected', 'Corregida'),
        ('justified', 'Justificada'),
    ], string='Estado de revisión', default='pending', index=True)
    review_note = fields.Text(string='Nota de revisión')
    reviewed_by = fields.Many2one('res.users', string='Revisada por', readonly=True)
    reviewed_at = fields.Datetime(string='Fecha de revisión', readonly=True)

    @api.depends('meter_id', 'meter_route', 'meter_owner_name')
    def _compute_meter_links(self):
        for rec in self:
            href = f'/web#id={rec.meter_id.id}&model=water.meter&view_type=form'
            rec.meter_route_link = (
                f'<a href="{href}">{escape(rec.meter_route or "")}</a>'
                if rec.meter_id else ''
            )
            rec.meter_owner_link = (
                f'<a href="{href}">{escape(rec.meter_owner_name or "")}</a>'
                if rec.meter_id else ''
            )
    history_reading_ids = fields.Many2many(
        'water.reading',
        relation='water_mobile_history_rel',
        column1='reading_id',
        column2='history_id',
        compute='_compute_history_readings',
        string='Últimas lecturas',
    )

    @api.depends('period_id', 'period_id.reading_ids.reading_current')
    def _compute_mobile_progress(self):
        for rec in self:
            if not rec.period_id:
                rec.mobile_progress = ''
                continue
            readings = rec.period_id.reading_ids
            pending = len(readings.filtered(lambda reading: reading.reading_current == 0))
            rec.mobile_progress = _('%(pending)s pendientes de %(total)s') % {
                'pending': pending,
                'total': len(readings),
            }

    @api.depends('meter_id')
    def _compute_history_readings(self):
        for rec in self:
            readings = self.search(
                [('meter_id', '=', rec.meter_id.id)],
                order='date desc, id desc',
                limit=4,
            ) if rec.meter_id else self.browse()
            rec.history_reading_ids = [(6, 0, readings.ids)]

    @api.depends_context('uid')
    def _compute_allow_edit_previous(self):
        user = self.env.user.sudo()
        can_edit = user.can_edit_readings or user.has_group('water_meter_reading.group_water_supervisor')
        for rec in self:
            rec.allow_edit_previous = can_edit

    @api.depends('reading_current', 'reading_previous', 'meter_reversed', 'meter_max_value')
    def _compute_difference(self):
        for rec in self:
            diff = rec.reading_current - rec.reading_previous
            if rec.meter_reversed and diff < 0 and rec.meter_max_value > 0:
                # Rollover: (max+1 - anterior) + actual
                diff = (rec.meter_max_value + 1 - rec.reading_previous) + rec.reading_current
            rec.difference = diff

    def action_estimate_current(self):
        self.ensure_one()
        if self.period_id and self.period_id.state == 'closed':
            raise ValidationError(_('No se puede estimar una lectura en un período cerrado.'))
        if self.reading_current:
            raise ValidationError(_('La lectura actual ya tiene un valor.'))
        previous_readings = self.search([
            ('meter_id', '=', self.meter_id.id),
            ('id', '!=', self.id),
            ('reading_current', '>', 0),
        ])
        if self.period_id:
            previous_readings = previous_readings.filtered(
                lambda reading: reading.period_id and (
                    reading.period_id.year < self.period_id.year
                    or (
                        reading.period_id.year == self.period_id.year
                        and int(reading.period_id.trimester) < int(self.period_id.trimester)
                    )
                )
            )
        previous_readings = previous_readings.sorted(
            key=lambda reading: (
                reading.period_id.year if reading.period_id else 0,
                int(reading.period_id.trimester) if reading.period_id else 0,
                reading.id,
            ),
            reverse=True,
        )[:4]
        if not previous_readings:
            raise ValidationError(_('No se puede estimar: no existen lecturas anteriores.'))
        consumptions = [reading.difference for reading in previous_readings if reading.difference >= 0]
        if not consumptions:
            raise ValidationError(_('No se puede estimar: no existen consumos válidos anteriores.'))
        average_consumption = round(sum(consumptions) / len(consumptions))
        base_reading = self.reading_previous or previous_readings[0].reading_current
        estimated_current = base_reading + average_consumption
        estimated_periods = [reading.period_id.display_name for reading in previous_readings if reading.estimated_reading]
        note = _(
            'Estimación basada en %(count)s período(s) anteriores. '
            'Consumo medio: %(average)s.'
        ) % {'count': len(consumptions), 'average': average_consumption}
        warning = False
        if estimated_periods:
            warning = _(
                'Aviso: ya fue estimada en el período anterior (%s). '
                'Revisa el resultado con especial atención.'
            ) % ', '.join(estimated_periods)
            note += ' ' + warning
        self.with_context(skip_estimation_reset=True).write({
            'reading_current': estimated_current,
            'estimated_reading': True,
            'estimated_note': note,
            'estimated_by': self.env.user.id,
            'estimated_at': fields.Datetime.now(),
        })
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Lectura estimada'),
                'message': warning or _('Lectura actual estimada: %s.') % estimated_current,
                'type': 'warning' if warning else 'success',
                'sticky': bool(warning),
            },
        }

    def _get_anomaly_values(self):
        self.ensure_one()
        severity = 'none'
        reasons = []
        unchanged = False

        def add_reason(level, reason):
            nonlocal severity
            priorities = {'none': 0, 'medium': 1, 'high': 2, 'critical': 3}
            if priorities[level] > priorities[severity]:
                severity = level
            reasons.append(reason)

        if self.reading_current == 0:
            add_reason('medium', _('Lectura actual pendiente o igual a cero.'))
        elif self.difference < 0:
            add_reason('critical', _('La lectura actual es inferior a la anterior.'))
        elif self.reading_previous > 0 and self.reading_current == self.reading_previous:
            unchanged = True
            add_reason('medium', _('La lectura no ha cambiado desde el período anterior.'))

        history_domain = [
            ('meter_id', '=', self.meter_id.id),
            ('id', '!=', self.id),
            ('reading_current', '>', 0),
            ('difference', '>', 0),
        ]
        if self.period_id:
            history_domain += [
                '|',
                ('period_id.year', '<', self.period_id.year),
                '&',
                ('period_id.year', '=', self.period_id.year),
                ('period_id.trimester', '<', self.period_id.trimester),
            ]
        history = self.search(history_domain, order='date desc, id desc', limit=4)
        historical_average = sum(history.mapped('difference')) / len(history) if history else 0
        if self.difference > 0 and historical_average:
            if self.difference >= 100 and self.difference >= historical_average * 5:
                add_reason(
                    'critical',
                    _('Consumo %(current)s: supera cinco veces la media histórica (%(average).1f).') % {
                        'current': self.difference,
                        'average': historical_average,
                    },
                )
            elif self.difference >= 50 and self.difference >= historical_average * 3:
                add_reason(
                    'high',
                    _('Consumo %(current)s: supera tres veces la media histórica (%(average).1f).') % {
                        'current': self.difference,
                        'average': historical_average,
                    },
                )
        elif self.difference >= 500:
            add_reason('critical', _('Consumo muy elevado sin histórico suficiente: %s.') % self.difference)
        elif self.difference >= 100:
            add_reason('high', _('Consumo elevado sin histórico suficiente: %s.') % self.difference)

        if self.meter_missing:
            add_reason('high', _('El suministro está marcado sin contador.'))
        if self.meter_broken:
            add_reason('high', _('El contador está marcado como roto.'))
        if severity in ('high', 'critical') and not self.counter_photo and not self.photo_ids:
            reasons.append(_('La incidencia no tiene fotografía.'))

        return {
            'anomaly_severity': severity,
            'anomaly_reason': '\n'.join(reasons) if reasons else False,
            'anomaly_unchanged': unchanged,
        }

    def _refresh_anomalies(self):
        for reading in self:
            values = reading._get_anomaly_values()
            anomaly_changed = (
                reading.anomaly_severity != values['anomaly_severity']
                or reading.anomaly_reason != values['anomaly_reason']
                or reading.anomaly_unchanged != values['anomaly_unchanged']
            )
            if anomaly_changed and reading.review_status != 'pending':
                values.update({
                    'review_status': 'pending',
                    'reviewed_by': False,
                    'reviewed_at': False,
                })
            reading.write(values)
        return True

    @api.onchange('reading_current', 'reading_previous', 'meter_reversed')
    def _onchange_reading_order(self):
        for rec in self:
            if (
                rec.reading_current
                and rec.reading_previous
                and rec.reading_current < rec.reading_previous
                and not rec.meter_reversed
            ):
                return {
                    'warning': {
                        'title': _('Lectura no válida'),
                        'message': _(
                            'La lectura actual no puede ser inferior a la lectura anterior. '
                            'Marca «Contador dio la vuelta» si el contador ha pasado por cero.'
                        ),
                    }
                }

    @api.constrains('reading_current', 'reading_previous', 'meter_reversed')
    def _check_reading_order(self):
        for rec in self:
            if (
                rec.reading_current
                and rec.reading_previous
                and rec.reading_current < rec.reading_previous
                and not rec.meter_reversed
            ):
                raise ValidationError(
                    _(
                        'La lectura actual no puede ser inferior a la lectura anterior. '
                        'Marca «Contador dio la vuelta» si el contador ha pasado por cero.'
                    )
                )

    @api.onchange('new_meter')
    def _onchange_new_meter(self):
        if self.new_meter:
            self.previous_meter_number = self.meter_id.meter_number
        else:
            self.previous_meter_number = False
            self.new_meter_number = False

    @api.constrains('new_meter', 'new_meter_number')
    def _check_new_meter_number(self):
        for rec in self:
            if rec.new_meter and not rec.new_meter_number:
                raise ValidationError(_('Debes indicar el número del contador nuevo.'))

    @api.constrains('meter_reversed', 'meter_max_value', 'reading_previous', 'reading_current')
    def _check_reversed_meter_range(self):
        for rec in self:
            if not rec.meter_reversed:
                continue
            if rec.meter_max_value <= 0:
                raise ValidationError(_('El valor máximo del contador debe ser mayor que cero.'))
            if rec.reading_previous > rec.meter_max_value or rec.reading_current > rec.meter_max_value:
                raise ValidationError(
                    _('Las lecturas no pueden superar el valor máximo del contador.')
                )

    def _apply_meter_replacement(self):
        for rec in self.filtered(lambda reading: reading.new_meter and reading.new_meter_number):
            new_number = rec.new_meter_number.strip()
            if new_number != rec.meter_id.meter_number:
                number_owner = self.env['water.meter'].with_context(active_test=False).search([
                    ('meter_number', '=', new_number),
                    ('id', '!=', rec.meter_id.id),
                ], limit=1)
                if number_owner:
                    raise ValidationError(
                        _('El contador %(meter)s ya pertenece al abonado %(subscriber)s.') % {
                            'meter': new_number,
                            'subscriber': number_owner.subscriber or '-',
                        }
                    )
                old_number = rec.meter_id.meter_number
                rec.with_context(skip_meter_replacement=True).write({
                    'previous_meter_number': rec.previous_meter_number or old_number,
                    'meter_number': new_number,
                    'new_meter_number': new_number,
                })
                rec.meter_id.write({'meter_number': new_number})

    def _mobile_action(self):
        self.ensure_one()
        view = self.env.ref('water_meter_reading.view_water_reading_mobile_form')
        return {
            'type': 'ir.actions.act_window',
            'name': _('Lectura de contador'),
            'res_model': self._name,
            'res_id': self.id,
            'views': [(view.id, 'form')],
            'target': 'current',
            'context': {'form_view_initial_mode': 'edit'},
        }

    def action_open_meter(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Contador'),
            'res_model': 'water.meter',
            'res_id': self.meter_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_mobile_done(self):
        self.ensure_one()
        view = self.env.ref('water_meter_reading.view_water_reading_mobile_selector_form')
        return {
            'type': 'ir.actions.act_window',
            'name': _('Seleccionar contador'),
            'res_model': 'water.reading.mobile.selector',
            'views': [(view.id, 'form')],
            'target': 'current',
            'context': {
                'default_period_id': self.period_id.id,
                'default_route': self.meter_route,
                'default_only_pending': True,
            },
        }

    def action_mobile_next(self):
        self.ensure_one()
        pending_readings = self.period_id.reading_ids.filtered(
            lambda reading: reading.reading_current == 0 and reading.id != self.id
        )
        current_street = (self.meter_id.street or self.meter_id.address or '').strip().casefold()
        pending_readings = pending_readings.filtered(
            lambda reading: (
                (reading.meter_id.street or reading.meter_id.address or '').strip().casefold()
                == current_street
            )
        )

        def route_key(reading):
            route = (reading.meter_route or '').strip()
            return (0, int(route), '') if route.isdigit() else (1, route.casefold(), '')

        ordered_pending = pending_readings.sorted(key=route_key)
        current_key = route_key(self)
        next_reading = next(
            (reading for reading in ordered_pending if route_key(reading) > current_key),
            None,
        )
        if not next_reading and ordered_pending:
            next_reading = ordered_pending[0]
        if next_reading:
            return next_reading._mobile_action()
        return self.action_mobile_done()

    @api.onchange('meter_id', 'period_id')
    def _onchange_meter_id(self):
        if not self.meter_id:
            return
        prev_value = 0
        if self.period_id:
            # Look in the previous period for this meter's reading
            period = self.period_id
            t = int(period.trimester)
            prev_t, prev_y = ('4', period.year - 1) if t == 1 else (str(t - 1), period.year)
            prev_period = self.env['water.period'].search(
                [('trimester', '=', prev_t), ('year', '=', prev_y)], limit=1
            )
            if prev_period:
                prev_reading = self.env['water.reading'].search(
                    [('meter_id', '=', self.meter_id.id),
                     ('period_id', '=', prev_period.id)], limit=1
                )
                if prev_reading:
                    prev_value = prev_reading.reading_current
        if not prev_value:
            # Fallback: generic last reading excluding current period
            last = self.env['water.reading'].search(
                [('meter_id', '=', self.meter_id.id),
                 ('period_id', '!=', self.period_id.id if self.period_id else False)],
                order='date desc, create_date desc', limit=1
            )
            prev_value = last.reading_current if last else 0
        self.reading_previous = prev_value

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('meter_id') and not vals.get('meter_number'):
                vals['meter_number'] = self.env['water.meter'].browse(vals['meter_id']).meter_number
            if vals.get('meter_id') and 'reading_previous' not in vals:
                prev_value = 0
                period_id = vals.get('period_id')
                if period_id:
                    period = self.env['water.period'].browse(period_id)
                    t = int(period.trimester)
                    prev_t = '4' if t == 1 else str(t - 1)
                    prev_y = period.year - 1 if t == 1 else period.year
                    prev_period = self.env['water.period'].search(
                        [('trimester', '=', prev_t), ('year', '=', prev_y)], limit=1
                    )
                    if prev_period:
                        prev_reading = self.search(
                            [('meter_id', '=', vals['meter_id']),
                             ('period_id', '=', prev_period.id)], limit=1
                        )
                        if prev_reading:
                            prev_value = prev_reading.reading_current
                if not prev_value:
                    last = self.search(
                        [('meter_id', '=', vals['meter_id']),
                         ('period_id', '!=', period_id)],
                        order='date desc, create_date desc', limit=1
                    )
                    prev_value = last.reading_current if last else 0
                vals['reading_previous'] = prev_value
            if not vals.get('name'):
                vals['name'] = self.env['ir.sequence'].next_by_code('water.reading') or '/'
        records = super().create(vals_list)
        records._apply_meter_replacement()
        return records

    def write(self, vals):
        if 'reading_current' in vals and not self.env.context.get('skip_estimation_reset'):
            vals = dict(vals, estimated_reading=False, estimated_note=False, estimated_by=False, estimated_at=False)
        if 'review_status' in vals:
            if vals['review_status'] == 'pending':
                vals.update({'reviewed_by': False, 'reviewed_at': False})
            else:
                vals.update({'reviewed_by': self.env.user.id, 'reviewed_at': fields.Datetime.now()})
        result = super().write(vals)
        if not self.env.context.get('skip_meter_replacement') and {
            'new_meter', 'new_meter_number'
        } & set(vals):
            self._apply_meter_replacement()
        return result
