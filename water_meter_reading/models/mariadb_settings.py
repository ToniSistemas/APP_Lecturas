from odoo import _, fields, models
from odoo.exceptions import UserError


class WaterMeterMariaDBSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    mariadb_host = fields.Char(
        string='Servidor MariaDB',
        config_parameter='water_meter_reading.mariadb_host',
    )
    mariadb_port = fields.Integer(
        string='Puerto MariaDB',
        default=3306,
        config_parameter='water_meter_reading.mariadb_port',
    )
    mariadb_database = fields.Char(
        string='Base de datos MariaDB',
        config_parameter='water_meter_reading.mariadb_database',
    )
    mariadb_user = fields.Char(
        string='Usuario MariaDB',
        config_parameter='water_meter_reading.mariadb_user',
    )
    mariadb_password = fields.Char(
        string='Contraseña MariaDB',
        config_parameter='water_meter_reading.mariadb_password',
        password=True,
    )

    def action_test_mariadb_connection(self):
        self.ensure_one()
        self.execute()
        try:
            import pymysql
        except ImportError as error:
            raise UserError(_("Falta instalar la librería Python 'PyMySQL' en el servidor Odoo.")) from error
        if not all((self.mariadb_host, self.mariadb_database, self.mariadb_user)):
            raise UserError(_('Completa servidor, base de datos y usuario MariaDB.'))
        try:
            connection = pymysql.connect(
                host=self.mariadb_host,
                port=self.mariadb_port or 3306,
                user=self.mariadb_user,
                password=self.mariadb_password or '',
                database=self.mariadb_database,
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
            raise UserError(_('No se pudo conectar a MariaDB: %s') % error) from error
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
