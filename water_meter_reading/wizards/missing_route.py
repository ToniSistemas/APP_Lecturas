from odoo import _, fields, models
from odoo.exceptions import ValidationError


class WaterMeterMissingRoute(models.TransientModel):
    _name = 'water.meter.missing.route'
    _description = 'Asignar rutas faltantes'

    import_id = fields.Many2one('water.meter.import', required=True, ondelete='cascade')
    line_ids = fields.One2many('water.meter.missing.route.line', 'wizard_id')

    def action_continue(self):
        self.ensure_one()
        missing = self.line_ids.filtered(lambda line: not line.route.strip())
        if missing:
            raise ValidationError(_('Completa todas las rutas antes de continuar.'))
        route_values = {line.row_number: line.route.strip() for line in self.line_ids}
        return self.import_id.with_context(missing_routes=route_values).action_import()


class WaterMeterMissingRouteLine(models.TransientModel):
    _name = 'water.meter.missing.route.line'
    _description = 'Fila con ruta faltante'

    wizard_id = fields.Many2one('water.meter.missing.route', required=True, ondelete='cascade')
    row_number = fields.Integer(string='Fila', readonly=True)
    meter_number = fields.Char(string='Contador', readonly=True)
    owner_name = fields.Char(string='Nombre', readonly=True)
    subscriber = fields.Char(string='Abonado', readonly=True)
    street = fields.Char(string='Calle', readonly=True)
    location = fields.Char(string='Ubicación', readonly=True)
    route = fields.Char(string='Ruta')