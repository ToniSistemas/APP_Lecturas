from odoo import api, fields, models


class WaterReadingMobileRoute(models.Model):
    _name = 'water.reading.mobile.route'
    _description = 'Ruta del selector móvil'
    _rec_name = 'name'
    _order = 'route_order asc, name asc'

    name = fields.Char(required=True)
    route_order = fields.Integer(string='Orden', index=True)
    period_id = fields.Many2one('water.period', index=True, ondelete='cascade')
    active = fields.Boolean(default=True)
    meter_number = fields.Char(string='Contador', readonly=True)
    owner_name = fields.Char(string='Nombre', readonly=True)
    subscriber = fields.Char(string='Abonado', readonly=True)
    street = fields.Char(string='Calle', readonly=True)
    pueblo = fields.Char(string='Pueblo', readonly=True)
    location = fields.Char(string='Ubicación', readonly=True)

    _unique_period_name = models.UniqueIndex(
        '(period_id, name)',
        'La ruta ya existe en este período.',
    )

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        routes = self.search(
            (args or []) + ([('name', operator, name)] if name else []),
            limit=limit,
        ).sorted(key=lambda route: (route.route_order, route.name))
        return [(route.id, route.display_name) for route in routes]
