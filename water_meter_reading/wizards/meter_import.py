import base64
import csv
import io
import unicodedata

from odoo import _, fields, models
from odoo.exceptions import UserError, ValidationError


class WaterMeterImport(models.TransientModel):
    _name = 'water.meter.import'
    _description = 'Importar contadores de agua'

    file = fields.Binary(string='Archivo', required=True)
    filename = fields.Char(string='Nombre del archivo')
    period_id = fields.Many2one('water.period', string='Período', required=True)
    confirmation_required = fields.Boolean(readonly=True)
    warning_message = fields.Text(string='Lecturas diferentes', readonly=True)

    _column_fields = {
        'Ruta': 'name',
        'Contador': 'meter_number',
        'Nombre': 'owner_name',
        'Abonado': 'subscriber',
        'Referencia catastral': 'cadastral_ref',
        'Dirección': 'address',
        'C.P.': 'zip',
        'Municipio': 'municipality',
        'Contador nuevo': 'new_meter',
        'Tipo de contador': 'meter_type',
        'Lectura anterior': 'reading_previous',
    }
    _required_headers = {'Ruta', 'Contador', 'Nombre'}

    _meter_types = {
        'DOM': 'dom',
        'DOMESTICO': 'dom',
        'DOMÉSTICO': 'dom',
        'ASIM': 'asim',
        'ASIMILADO': 'asim',
        'NDOM': 'ndom',
        'NO DOMESTICO': 'ndom',
        'NO DOMÉSTICO': 'ndom',
        'ESP': 'esp',
        'ESPECIAL': 'esp',
    }

    @staticmethod
    def _normalize_header(value):
        text = ''.join(str(value or '').replace('\xa0', ' ').split()).casefold()
        return ''.join(
            character for character in unicodedata.normalize('NFKD', text)
            if not unicodedata.combining(character)
        )

    def _parse_boolean(self, value, row_number):
        normalized = value.strip().lower()
        if not normalized:
            return False
        if normalized in ('1', 'sí', 'si', 'true', 'verdadero', 'x'):
            return True
        if normalized in ('0', 'no', 'false', 'falso'):
            return False
        raise ValidationError(
            _('Fila %s: Contador nuevo debe indicar Sí/No, True/False o 1/0.') % row_number
        )

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
            headers = [self._normalize_header(header) for header in headers]
            return [
                dict(zip(headers, values))
                for values in rows
                if any(value not in (None, '') for value in values)
            ]
        raise UserError(_('El archivo debe tener formato CSV o XLSX.'))

    def _confirmation_action(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Confirmar importación del censo'),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_import_confirmed(self):
        self.ensure_one()
        return self.with_context(confirm_reading_mismatches=True).action_import()

    def action_import(self):
        self.ensure_one()
        if self.period_id.state == 'closed':
            raise UserError(_('No se puede importar el censo en un período cerrado.'))
        rows = self._read_rows()
        if not rows:
            raise UserError(_('El archivo no contiene contadores para importar.'))

        normalized_rows = [
            {self._normalize_header(header): value for header, value in row.items()}
            for row in rows
        ]
        required_headers = {self._normalize_header(header) for header in self._required_headers}
        missing_headers = required_headers - set(normalized_rows[0])
        if missing_headers:
            raise ValidationError(
                _('Faltan columnas obligatorias: %s') % ', '.join(sorted(missing_headers)).title()
            )

        available_fields = {
            field
            for header, field in self._column_fields.items()
            if self._normalize_header(header) in normalized_rows[0]
        }
        imported_rows = []
        meter_numbers = set()
        routes = set()
        for row_number, row in enumerate(normalized_rows, start=2):
            values = {
                field: row.get(self._normalize_header(header), '')
                for header, field in self._column_fields.items()
                if field in available_fields
            }
            values = {
                field: str(value).strip() if value is not None else ''
                for field, value in values.items()
            }
            if not values['name'] or not values['meter_number'] or not values['owner_name']:
                raise ValidationError(_('Fila %s: Ruta, Contador y Nombre son obligatorios.') % row_number)
            if values['name'] in routes:
                raise ValidationError(_('Fila %s: la ruta %s está repetida en el archivo.') % (
                    row_number, values['name']))
            if values['meter_number'] in meter_numbers:
                raise ValidationError(_('Fila %s: el contador %s está repetido en el archivo.') % (
                    row_number, values['meter_number']))
            if 'new_meter' in values:
                values['new_meter'] = self._parse_boolean(values['new_meter'], row_number)
            if 'meter_type' in values:
                meter_type = values['meter_type'].upper()
                if meter_type and meter_type not in self._meter_types:
                    raise ValidationError(
                        _('Fila %s: Tipo de contador debe ser DOM, ASIM, NDOM o ESP.') % row_number
                    )
                values['meter_type'] = self._meter_types.get(meter_type, False)
            previous_reading = values.pop('reading_previous', False)
            if previous_reading:
                try:
                    previous_reading = int(previous_reading)
                except (TypeError, ValueError) as error:
                    raise ValidationError(_('Fila %s: Lectura anterior debe ser un número entero.') % row_number) from error
                if previous_reading < 0:
                    raise ValidationError(_('Fila %s: Lectura anterior no puede ser negativa.') % row_number)
            else:
                previous_reading = False
            routes.add(values['name'])
            meter_numbers.add(values['meter_number'])
            imported_rows.append((values, previous_reading))

        Meter = self.env['water.meter'].with_context(active_test=False)
        existing_by_number = {
            meter.meter_number: meter
            for meter in Meter.search([('meter_number', 'in', list(meter_numbers))])
        }
        existing_by_route = {
            meter.name: meter
            for meter in Meter.search([('name', 'in', list(routes))])
        }

        previous_period = self.period_id._get_previous_period()
        previous_by_meter = {}
        if previous_period:
            previous_by_meter = {
                reading.meter_id.id: reading.reading_current
                for reading in self.env['water.reading'].search([
                    ('period_id', '=', previous_period.id),
                    ('meter_id', 'in', [meter.id for meter in existing_by_number.values()]),
                ])
            }
        mismatches = []
        for values, imported_previous in imported_rows:
            meter = existing_by_number.get(values['meter_number'])
            if not meter or imported_previous is False or meter.id not in previous_by_meter:
                continue
            stored_current = previous_by_meter[meter.id]
            if imported_previous != stored_current:
                mismatches.append(
                    _('%(meter)s (%(subscriber)s): guardada %(stored)s, Excel %(imported)s') % {
                        'meter': meter.meter_number,
                        'subscriber': meter.subscriber or meter.owner_name or '-',
                        'stored': stored_current,
                        'imported': imported_previous,
                    }
                )
        if mismatches and not self.env.context.get('confirm_reading_mismatches'):
            shown_mismatches = mismatches[:50]
            if len(mismatches) > 50:
                shown_mismatches.append(_('... y %s diferencias más.') % (len(mismatches) - 50))
            self.write({
                'confirmation_required': True,
                'warning_message': _(
                    'La lectura anterior del Excel no coincide con la lectura actual de '
                    '%(period)s para estos contadores:\n\n%(differences)s'
                ) % {
                    'period': previous_period.name,
                    'differences': '\n'.join(shown_mismatches),
                },
            })
            return self._confirmation_action()

        meters = []
        created_count = 0
        updated_count = 0
        for values, previous_reading in imported_rows:
            meter = existing_by_number.get(values['meter_number'])
            route_owner = existing_by_route.get(values['name'])
            if route_owner and route_owner != meter:
                raise ValidationError(
                    _('La ruta %(route)s ya pertenece al contador %(meter)s.') % {
                        'route': values['name'],
                        'meter': route_owner.meter_number,
                    }
                )
            if meter:
                update_values = dict(values, active=True)
                changed_values = {
                    field: value
                    for field, value in update_values.items()
                    if meter[field] != value
                }
                if changed_values:
                    meter.write(changed_values)
                    updated_count += 1
            else:
                meter = Meter.with_context(skip_initial_reading=True).create(dict(values, active=True))
                existing_by_number[meter.meter_number] = meter
                existing_by_route[meter.name] = meter
                created_count += 1
            meters.append((meter, previous_reading))

        Reading = self.env['water.reading']
        readings_by_meter = {
            reading.meter_id.id: reading
            for reading in Reading.search([
                ('period_id', '=', self.period_id.id),
                ('meter_id', 'in', [meter.id for meter, _previous in meters]),
            ])
        }
        reading_count = 0
        for meter, previous_reading in meters:
            reading = readings_by_meter.get(meter.id)
            if reading:
                if previous_reading is not False and reading.reading_previous != previous_reading:
                    reading.reading_previous = previous_reading
                continue
            reading_values = {
                'meter_id': meter.id,
                'period_id': self.period_id.id,
                'date': fields.Date.context_today(self),
            }
            if previous_reading is not False:
                reading_values['reading_previous'] = previous_reading
            Reading.create(reading_values)
            reading_count += 1

        if self.period_id.state == 'draft':
            self.period_id.state = 'open'

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Importación completada'),
                'message': _(
                    '%(created)s contadores creados, %(updated)s actualizados y '
                    '%(readings)s añadidos al período %(period)s.'
                ) % {
                    'created': created_count,
                    'updated': updated_count,
                    'readings': reading_count,
                    'period': self.period_id.name,
                },
                'type': 'success',
                'sticky': False,
            },
        }