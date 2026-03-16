{
    'name': 'Water Meter Readings',
    'version': '18.0.1.0.0',
    'summary': 'Registro de lecturas de contadores de agua',
    'category': 'Tools',
    'author': 'Toni',
    'license': 'LGPL-3',
    'depends': ['base', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'views/water_meter_views.xml',
        'data/sequence_data.xml',
    ],
    'installable': True,
    'application': True,
}
