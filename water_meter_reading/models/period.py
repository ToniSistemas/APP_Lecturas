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
    show_unread = fields.Boolean(string='Mostrar solo contadores sin leer', default=False)
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('open', 'Abierto'),
        ('closed', 'Cerrado'),
    ], string='Estado', default='draft', readonly=True)
    reading_ids = fields.One2many('water.reading', 'period_id', string='Lecturas')
    unread_reading_ids = fields.One2many(
        'water.reading',
        'period_id',
        string='Lecturas sin leer',
        compute='_compute_unread_reading_ids',
    )
    reading_count = fields.Integer(compute='_compute_reading_count', string='Lecturas')
    pending_count = fields.Integer(compute='_compute_reading_counts', string='Contadores pendientes')
    read_count = fields.Integer(compute='_compute_reading_counts', string='Contadores leídos')

    @api.depends('trimester', 'year')
    def _compute_name(self):
        for rec in self:
            rec.name = f"{rec.trimester}T{rec.year}" if rec.trimester and rec.year else ''

    @api.depends('reading_ids')
    def _compute_reading_count(self):
        for rec in self:
            rec.reading_count = len(rec.reading_ids)

    @api.depends('reading_ids.reading_current')
    def _compute_reading_counts(self):
        for rec in self:
            rec.pending_count = len(rec.reading_ids.filtered(lambda reading: reading.reading_current == 0))
            rec.read_count = len(rec.reading_ids.filtered(lambda reading: reading.reading_current != 0))

    @api.depends('reading_ids', 'reading_ids.reading_current')
    def _compute_unread_reading_ids(self):
        for rec in self:
            rec.unread_reading_ids = rec.reading_ids.filtered(
                lambda reading: reading.reading_current == 0
            )

    def _get_previous_period(self):
        """Devuelve el período inmediatamente anterior a este, o False si no existe."""
        t = int(self.trimester)
        if t == 1:
            prev_t, prev_y = '4', self.year - 1
        else:
            prev_t, prev_y = str(t - 1), self.year
        return self.search([('trimester', '=', prev_t), ('year', '=', prev_y)], limit=1)

    def action_open_meter_import(self):
        self.ensure_one()
        if self.state == 'closed':
            raise UserError(_('No se puede importar el censo en un período cerrado.'))
        connection = self.env['water.mariadb.connection'].search([('active', '=', True)], limit=1)
        if not connection:
            raise UserError(_('Configura primero una conexión MariaDB activa.'))
        rows = connection.fetch_readings(int(self.year), int(self.trimester))
        if not rows:
            raise UserError(_('No hay datos en MariaDB para %(year)s, período %(period)s.') % {
                'year': self.year,
                'period': self.trimester,
            })
        return self.env['water.meter.import'].with_context(
            default_period_id=self.id,
        ).create({
            'period_id': self.id,
            'import_readings': False,
        }).action_import_rows(rows, import_readings=False)

    def action_open_read_meter_import(self):
        self.ensure_one()
        if self.state == 'closed':
            raise UserError(_('No se puede importar en un período cerrado.'))
        if not self.env.user.has_group('water_meter_reading.group_water_supervisor'):
            raise AccessError(_('Solo los supervisores pueden importar censos ya leídos.'))
        connection = self.env['water.mariadb.connection'].search([('active', '=', True)], limit=1)
        if not connection:
            raise UserError(_('Configura primero una conexión MariaDB activa.'))
        rows = connection.fetch_readings(int(self.year), int(self.trimester))
        if not rows:
            raise UserError(_('No hay lecturas en MariaDB para %(year)s, período %(period)s.') % {
                'year': self.year,
                'period': self.trimester,
            })
        return self.env['water.meter.import'].with_context(
            default_period_id=self.id,
            default_import_readings=True,
        ).create({
            'period_id': self.id,
            'import_readings': True,
        }).action_import_rows(rows, import_readings=True)

    def action_open_gtb_update(self):
        self.ensure_one()
        if self.state == 'closed':
            raise UserError(_('No se puede actualizar un período cerrado.'))
        if not (
            self.env.user.has_group('base.group_system')
            or self.env.user.has_group('water_meter_reading.group_water_supervisor')
        ):
            raise AccessError(_('Solo administradores y supervisores pueden actualizar datos GTB.'))
        connection = self.env['water.mariadb.connection'].search([('active', '=', True)], limit=1)
        if not connection:
            raise UserError(_('Configura primero una conexión MariaDB activa.'))
        rows = connection.fetch_readings(int(self.year), int(self.trimester))
        if not rows:
            raise UserError(_('No hay datos GTB en MariaDB para este período.'))
        wizard = self.env['water.meter.gtb.update'].create({'period_id': self.id})
        return wizard.action_prepare(rows)


    def action_start_mobile_readings(self):
        self.ensure_one()
        if not self.reading_ids:
            raise UserError(_('Importa primero el censo de contadores del período.'))
        self.env['water.reading.mobile.selector']._sync_streets(self.id)
        view = self.env.ref('water_meter_reading.view_water_reading_mobile_selector_form')
        return {
            'type': 'ir.actions.act_window',
            'name': _('Seleccionar contador'),
            'res_model': 'water.reading.mobile.selector',
            'views': [(view.id, 'form')],
            'target': 'current',
            'context': {
                'default_period_id': self.id,
                'default_only_pending': True,
            },
        }

    def action_review_anomalies(self):
        self.ensure_one()
        self.reading_ids._refresh_anomalies()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Anomalías - %s') % self.name,
            'res_model': 'water.reading',
            'view_mode': 'list,form',
            'views': [
                (self.env.ref('water_meter_reading.view_water_reading_list').id, 'list'),
                (self.env.ref('water_meter_reading.view_water_reading_form').id, 'form'),
            ],
            'domain': [
                ('period_id', '=', self.id),
                ('anomaly_severity', '!=', 'none'),
            ],
            'context': {'search_default_pending_anomaly_review': 1},
        }

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

    def action_export_excel(self):
        import io
        import base64
        import xlsxwriter

        self.ensure_one()
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        ws = workbook.add_worksheet('Lecturas')

        bold = workbook.add_format({'bold': True, 'bg_color': '#4472C4', 'font_color': '#FFFFFF'})
        date_fmt = workbook.add_format({'num_format': 'dd/mm/yyyy'})

        headers = ['Contador', 'Ruta', 'Nombre', 'Abonado', 'Municipio', 'C.P.',
                   'Referencia catastral', 'Fecha', 'Lectura anterior',
                   'Lectura actual', 'Diferencia', 'Observaciones']
        for col, h in enumerate(headers):
            ws.write(0, col, h, bold)
            ws.set_column(col, col, 15)
        ws.set_column(2, 2, 20)  # Nombre
        ws.set_column(11, 11, 30)  # Observaciones

        for row, r in enumerate(self.reading_ids, start=1):
            ws.write(row, 0, r.meter_number or '')
            ws.write(row, 1, r.meter_route or '')
            ws.write(row, 2, r.meter_owner_name or '')
            ws.write(row, 3, r.meter_id.subscriber or '')
            ws.write(row, 4, r.meter_municipality or '')
            ws.write(row, 5, r.meter_zip or '')
            ws.write(row, 6, r.meter_id.cadastral_ref or '')
            if r.date:
                ws.write_datetime(row, 7,
                    r.date.strftime('%Y-%m-%dT00:00:00') and
                    __import__('datetime').datetime.combine(r.date, __import__('datetime').time()),
                    date_fmt)
            else:
                ws.write(row, 7, '')
            ws.write(row, 8, r.reading_previous)
            ws.write(row, 9, r.reading_current)
            ws.write(row, 10, r.difference)
            ws.write(row, 11, r.observations or '')

        workbook.close()
        output.seek(0)
        xlsx_data = base64.b64encode(output.read())

        attachment = self.env['ir.attachment'].create({
            'name': f'Lecturas_{self.name}.xlsx',
            'type': 'binary',
            'datas': xlsx_data,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'res_model': self._name,
            'res_id': self.id,
        })
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'new',
        }

    def action_close(self):
        self.ensure_one()
        if not self.env.user.has_group('water_meter_reading.group_water_supervisor'):
            raise AccessError(_('Solo los supervisores pueden cerrar períodos.'))
        self.state = 'closed'

    def action_reopen(self):
        self.ensure_one()
        if not self.env.user.has_group('water_meter_reading.group_water_supervisor'):
            raise AccessError(_('Solo los supervisores pueden reabrir períodos.'))
        self.state = 'open'

    def write(self, vals):
        if 'state' in vals and not self.env.user.has_group('water_meter_reading.group_water_supervisor'):
            draft_to_open = vals['state'] == 'open' and all(record.state == 'draft' for record in self)
            if not draft_to_open:
                raise AccessError(_('Solo los supervisores pueden cerrar o reabrir períodos.'))
        return super().write(vals)

    def unlink(self):
        if not self.env.user.has_group('water_meter_reading.group_water_supervisor'):
            raise AccessError(_('Solo los supervisores pueden eliminar períodos.'))
        return super().unlink()

    def action_view_readings_search(self):
        self.ensure_one()
        domain = [('period_id', '=', self.id)]
        if self.show_unread:
            domain.append(('reading_current', '=', 0))
        return {
            'type': 'ir.actions.act_window',
            'name': f'Lecturas \u2013 {self.name}',
            'res_model': 'water.reading',
            'view_mode': 'list,form',
            'domain': domain,
            'context': {'default_period_id': self.id},
        }
