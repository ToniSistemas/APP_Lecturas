import base64
import csv
import io

from odoo import _, fields, models
from odoo.exceptions import UserError, ValidationError


class WaterMeterImport(models.TransientModel):
    _name = 'water.meter.import'
    _description = 'Importar contadores de agua'

    file = fields.Binary(string='Archivo', required=True)
    filename = fields.Char(string='Nombre del archivo')

    _column_fields = {
        'Ruta': 'name',
        'Contador': 'meter_number',
        'Nombre': 'owner_name',
        'Abonado': 'subscriber',
        'Referencia catastral': 'cadastral_ref',
        'Dirección': 'address',
        'C.P.': 'zip',
        'Municipio': 'municipality',
        'Lectura anterior': 'reading_previous',
    }
    _required_headers = {'Ruta', 'Nombre'}

    def _read_rows(self):
        self.ensure_one()
        content = base64.b64decode(self.file or b'')
        filename = (self.filename or '').lower()
        if filename.endswith('.csv'):
            text = content.decode('utf-8-sig')
            return list(csv.DictReader(io.StringIO(text)))
        if filename.endswith('.xlsx'):
            try:
                from openpyxl import load_workbook
            except ImportError as error:
                raise UserError(_("Para importar archivos XLSX debe instalarse la librería Python 'openpyxl'.")) from error
            workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
            sheet = workbook.active
            rows = sheet.iter_rows(values_only=True)
            headers = next(rows, None)
            if not headers:
                return []
            headers = [str(header).strip() if header is not None else '' for header in headers]
            return [
                dict(zip(headers, values))
                for values in rows
                if any(value not in (None, '') for value in values)
            ]
        raise UserError(_('El archivo debe tener formato CSV o XLSX.'))

    def action_import(self):
        self.ensure_one()
        rows = self._read_rows()
        if not rows:
            raise UserError(_('El archivo no contiene contadores para importar.'))

        headers = {str(header).strip() for header in rows[0]}
        missing_headers = self._required_headers - headers
        if missing_headers:
            raise ValidationError(
                _('Faltan columnas obligatorias: %s') % ', '.join(sorted(missing_headers))
            )

        period = self.env['water.period'].search(
            [('state', 'in', ('draft', 'open'))],
            order='year desc, trimester desc',
            limit=1,
        )

        meters_to_create = []
        previous_readings = []
        meter_numbers = set()
        routes = set()
        for row_number, row in enumerate(rows, start=2):
            values = {field: row.get(header, '') for header, field in self._column_fields.items()}
            values = {
                field: str(value).strip() if value is not None else ''
                for field, value in values.items()
            }
            if not values['name'] or not values['owner_name']:
                raise ValidationError(_('Fila %s: Ruta y Nombre son obligatorios.') % row_number)
            if values['name'] in routes:
                raise ValidationError(_('Fila %s: la ruta %s está repetida en el archivo.') % (
                    row_number, values['name']))
            if values['meter_number'] and values['meter_number'] in meter_numbers:
                raise ValidationError(_('Fila %s: el contador %s está repetido en el archivo.') % (
                    row_number, values['meter_number']))
            previous_reading = values.pop('reading_previous')
            if previous_reading:
                try:
                    previous_reading = int(previous_reading)
                except (TypeError, ValueError) as error:
                    raise ValidationError(_('Fila %s: Lectura anterior debe ser un número entero.') % row_number) from error
                if previous_reading < 0:
                    raise ValidationError(_('Fila %s: Lectura anterior no puede ser negativa.') % row_number)
            else:
                previous_reading = False
            if not values['meter_number']:
                values['meter_number'] = False
            routes.add(values['name'])
            if values['meter_number']:
                meter_numbers.add(values['meter_number'])
            meters_to_create.append(values)
            previous_readings.append(previous_reading)

        existing_meters = self.env['water.meter'].search([('meter_number', 'in', list(meter_numbers))])
        if existing_meters:
            raise ValidationError(_('Ya existen estos contadores: %s') % ', '.join(existing_meters.mapped('meter_number')))
        existing_routes = self.env['water.meter'].search([
            ('name', 'in', list(routes)),
        ])
        if existing_routes:
            raise ValidationError(_('Ya existen estas rutas: %s') % ', '.join(existing_routes.mapped('name')))

        meters = self.env['water.meter'].with_context(skip_initial_reading=True).create(meters_to_create)
        readings = []
        for meter, previous_reading in zip(meters, previous_readings):
            if previous_reading is False:
                continue
            if period:
                readings.append({
                    'meter_id': meter.id,
                    'period_id': period.id,
                    'reading_previous': previous_reading,
                    'date': fields.Date.context_today(self),
                })
            else:
                readings.append({
                    'meter_id': meter.id,
                    'reading_previous': previous_reading,
                    'reading_current': previous_reading,
                    'date': fields.Date.context_today(self),
                })
        if readings:
            self.env['water.reading'].create(readings)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Importación completada'),
                'message': _('%s contadores importados.') % len(meters),
                'type': 'success',
                'sticky': False,
            },
        }