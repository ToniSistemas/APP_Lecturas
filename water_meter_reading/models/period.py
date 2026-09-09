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

    def action_open_meter_import(self):
        self.ensure_one()
        if self.state == 'closed':
            raise UserError(_('No se puede importar el censo en un período cerrado.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Importar censo de contadores'),
            'res_model': 'water.meter.import',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_period_id': self.id},
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
