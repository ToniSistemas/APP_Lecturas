from odoo import _, fields, models


class WaterMeterMissingRoute(models.TransientModel):
    _name = 'water.meter.missing.route'
    _description = 'Asignar rutas faltantes'

    import_id = fields.Many2one('water.meter.import', required=True, ondelete='cascade')
    line_ids = fields.One2many('water.meter.missing.route.line', 'wizard_id')

    def action_continue(self):
        self.ensure_one()
        existing_routes = set(
            self.env['water.meter'].with_context(active_test=False).search([]).mapped('name')
        )
        route_values = {}
        used_routes = set(existing_routes)
        used_routes.update(
            (line.route or '').strip()
            for line in self.line_ids
            if (line.route or '').strip()
        )
        automatic_number = 1
        for line in self.line_ids.sorted('row_number'):
            route = (line.route or '').strip()
            if not route:
                while f'NR_{automatic_number}' in used_routes:
                    automatic_number += 1
                route = f'NR_{automatic_number}'
                automatic_number += 1
                line.route = route
            route_values[line.row_number] = route
            used_routes.add(route)
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