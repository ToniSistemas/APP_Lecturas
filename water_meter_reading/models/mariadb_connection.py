import re
import unicodedata

from odoo import _, fields, models
from odoo.exceptions import UserError


class WaterMeterMariaDBConnection(models.Model):
    _name = 'water.mariadb.connection'
    _description = 'Conexión MariaDB'
    _order = 'name, id'

    name = fields.Char(string='Nombre', required=True)
    host = fields.Char(string='Servidor', required=True)
    port = fields.Integer(string='Puerto', required=True, default=3306)
    database = fields.Char(string='Base de datos', required=True)
    user = fields.Char(string='Usuario', required=True)
    password = fields.Char(string='Contraseña', required=True)
    active = fields.Boolean(string='Activa', default=True)
    last_test_ok = fields.Boolean(string='Última prueba correcta', readonly=True)
    last_test_message = fields.Text(string='Resultado de la última prueba', readonly=True)
    last_test_date = fields.Datetime(string='Última prueba', readonly=True)
    sql_query = fields.Text(
        string='Consulta SQL personalizada',
        help='Opcional. Si está vacía se utiliza la consulta automática del módulo.',
    )
    last_sql_query = fields.Text(
        string='Última consulta ejecutada',
        readonly=True,
        help='SQL efectivo con Ejercicio y periodo sustituidos, listo para copiar.',
    )

    @staticmethod
    def _normalize_column(name):
        value = unicodedata.normalize('NFKD', str(name)).casefold()
        value = ''.join(char for char in value if not unicodedata.combining(char))
        return re.sub(r'[^a-z0-9]+', '', value)

    @classmethod
    def _find_column(cls, columns, *names):
        normalized = {cls._normalize_column(column): column for column in columns}
        for name in names:
            if cls._normalize_column(name) in normalized:
                return normalized[cls._normalize_column(name)]
        return False

    @staticmethod
    def _quote_column(column):
        return '`%s`' % column.replace('`', '``')

    @staticmethod
    def _query_for_display(query, params):
        display_query = query
        for value in params:
            replacement = str(value) if isinstance(value, int) else "'%s'" % str(value).replace("'", "''")
            display_query = display_query.replace('%s', replacement, 1)
        return display_query

    @staticmethod
    def _normalize_sql_start(query):
        query = query.lstrip('\ufeff \t\r\n')
        while True:
            without_block_comment = re.sub(r'^/\*.*?\*/', '', query, count=1, flags=re.S).lstrip()
            without_line_comment = re.sub(r'^(?:--|#)[^\r\n]*(?:\r?\n|$)', '', without_block_comment, count=1).lstrip()
            if without_line_comment == query:
                return query
            query = without_line_comment

    def fetch_readings(self, year, trimester):
        self.ensure_one()
        try:
            import pymysql
        except ImportError as error:
            raise UserError(_("Falta instalar la librería Python 'PyMySQL' en el servidor Odoo.")) from error
        connection = None
        try:
            connection = pymysql.connect(
                host=self.host,
                port=self.port or 3306,
                user=self.user,
                password=self.password or '',
                database=self.database,
                connect_timeout=5,
                read_timeout=30,
                write_timeout=5,
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor,
                read_default_file=None,
            )
            with connection.cursor() as cursor:
                cursor.execute('DESCRIBE `lecturas`')
                columns = [row['Field'] for row in cursor.fetchall()]
                required = {
                    'ruta': self._find_column(columns, 'Ruta'),
                    'contador': self._find_column(columns, 'Contador'),
                    'nombre': self._find_column(columns, 'Nombre'),
                    'abonado': self._find_column(columns, 'Abonado'),
                    'exercise': self._find_column(columns, 'Ejercicio', 'Año', 'Anho'),
                    'period': self._find_column(columns, 'periodo', 'Período', 'Trimestre'),
                }
                missing = [key for key, column in required.items() if not column]
                if missing:
                    raise UserError(_('Faltan columnas en MariaDB: %s') % ', '.join(missing))

                def expression(alias, *candidates):
                    column = self._find_column(columns, *candidates)
                    return self._quote_column(column) if column else 'NULL'

                location_columns = [
                    self._find_column(columns, candidate)
                    for candidate in (
                        'OBJ_ENTIDADCOLECTIVA', 'NÚMERO', 'NUMERO', 'PORTAL',
                        'PLANTA', 'ESCALERA', 'PUERTA',
                    )
                ]
                location_columns = list(dict.fromkeys(
                    column for column in location_columns if column
                ))
                location_parts = []
                previous_columns = []
                for column in location_columns:
                    quoted_column = self._quote_column(column)
                    duplicate_condition = ' OR '.join(
                        '%s = %s' % (quoted_column, self._quote_column(previous))
                        for previous in previous_columns
                    )
                    value = (
                        'CASE WHEN %s THEN NULL ELSE %s END' % (duplicate_condition, quoted_column)
                        if duplicate_condition else quoted_column
                    )
                    location_parts.append("NULLIF(%s, '')" % value)
                    previous_columns.append(column)
                location = (
                    'CONCAT_WS(\', \', %s)' % ', '.join(
                        location_parts
                    )
                    if location_columns else 'NULL'
                )
                generated_query = """SELECT
                    %(ruta)s AS ruta,
                    %(contador)s AS contador,
                    %(nombre)s AS nombre,
                    %(abonado)s AS abonado,
                    %(referencia)s AS referencia_catastral,
                    %(calle)s AS calle,
                    %(ubicacion)s AS ubicacion,
                    %(tipo)s AS tipo_contador,
                    %(anterior)s AS lectura_anterior,
                    %(actual)s AS lectura_actual,
                    %(consumo)s AS consumo
                    FROM `lecturas`
                    WHERE %(ejercicio)s = %%s AND %(periodo)s = %%s""" % {
                        'ruta': self._quote_column(required['ruta']),
                        'contador': self._quote_column(required['contador']),
                        'nombre': self._quote_column(required['nombre']),
                        'abonado': self._quote_column(required['abonado']),
                        'referencia': expression('referencia', 'Referencia catastral', 'Referencia_catastral'),
                        'calle': expression('calle', 'Calle', 'OBJ_ENTIDADCOLECTIVA'),
                        'ubicacion': location,
                        'tipo': expression(
                            'tipo', 'tipocanon', 'Tipo canon',
                            'Tipo de contador', 'Tipo_contador',
                        ),
                        'anterior': expression('anterior', 'Lectura anterior', 'Lectura_anterior', 'lectura_ant'),
                        'actual': expression('actual', 'Lectura actual', 'Lectura_actual', 'lectura_act'),
                        'consumo': expression('consumo', 'Consumo'),
                        'ejercicio': self._quote_column(required['exercise']),
                        'periodo': self._quote_column(required['period']),
                    }
                custom_query = self._normalize_sql_start(self.sql_query or '').strip()
                query = custom_query or generated_query
                query_params = (year, trimester)
                normalized_query = self._normalize_sql_start(query).casefold()
                if not re.match(r'^(select|with)\b', normalized_query):
                    query_type = 'personalizada' if custom_query else 'automática'
                    raise UserError(_('La consulta %s debe comenzar por SELECT o WITH.') % query_type)
                if ';' in query.rstrip().rstrip(';'):
                    raise UserError(_('La consulta personalizada no puede contener varias sentencias.'))
                forbidden = re.search(r'\b(insert|update|delete|drop|alter|truncate|create|replace|grant|revoke)\b', normalized_query)
                if forbidden:
                    raise UserError(_('La consulta contiene una operación no permitida: %s.') % forbidden.group(1))
                self.sudo().write({
                    'last_sql_query': self._query_for_display(query, query_params),
                })
                cursor.execute(query, query_params)
                return cursor.fetchall()
        except Exception as error:
            raise UserError(_('No se pudo leer la tabla lecturas: %s') % error) from error
        finally:
            if connection:
                connection.close()

    def action_test_connection(self):
        self.ensure_one()
        try:
            import pymysql
        except ImportError as error:
            raise UserError(_("Falta instalar la librería Python 'PyMySQL' en el servidor Odoo.")) from error
        try:
            connection = pymysql.connect(
                host=self.host,
                port=self.port or 3306,
                user=self.user,
                password=self.password or '',
                database=self.database,
                connect_timeout=5,
                read_timeout=5,
                write_timeout=5,
                charset='utf8mb4',
            )
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1')
                cursor.fetchone()
            connection.close()
        except Exception as error:
            self.write({
                'last_test_ok': False,
                'last_test_message': str(error),
                'last_test_date': fields.Datetime.now(),
            })
            raise UserError(_('No se pudo conectar a MariaDB: %s') % error) from error
        self.write({
            'last_test_ok': True,
            'last_test_message': _('Conexión correcta.'),
            'last_test_date': fields.Datetime.now(),
        })
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Conexión correcta'),
                'message': _('La conexión a MariaDB funciona correctamente.'),
                'type': 'success',
                'sticky': False,
            },
        }
