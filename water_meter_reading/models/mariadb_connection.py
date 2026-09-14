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
