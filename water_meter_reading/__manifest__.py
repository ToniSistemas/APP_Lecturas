{
    'name': 'Water Meter Readings',
    'version': '18.0.1.14.0',
    'summary': 'Registro de lecturas de contadores de agua',
    'category': 'Tools',
    'author': 'Toni',
    'license': 'LGPL-3',
    'depends': ['base', 'mail'],
    'assets': {
        'web.assets_backend': [
            'water_meter_reading/static/src/js/camera_image_field.js',
        ],
    },
    'data': [
        'security/groups.xml',
        'security/ir.model.access.csv',
        'views/res_users_views.xml',
        'views/water_meter_views.xml',
        'views/water_period_views.xml',
        'data/sequence_data.xml',
    ],
    'installable': True,
    'application': True,
}
