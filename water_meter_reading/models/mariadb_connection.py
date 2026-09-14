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
                location_columns = [column for column in location_columns if column]
                location = (
                    'CONCAT_WS(\', \', %s)' % ', '.join(
                        "NULLIF(%s, '')" % self._quote_column(column)
                        for column in location_columns
                    )
                    if location_columns else 'NULL'
                )
                query = """SELECT
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
                        'tipo': expression('tipo', 'Tipo de contador', 'Tipo_contador'),
                        'anterior': expression('anterior', 'Lectura anterior', 'Lectura_anterior'),
                        'actual': expression('actual', 'Lectura actual', 'Lectura_actual'),
                        'consumo': expression('consumo', 'Consumo'),
                        'ejercicio': self._quote_column(required['exercise']),
                        'periodo': self._quote_column(required['period']),
                    }
                cursor.execute(query, (year, trimester))
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
