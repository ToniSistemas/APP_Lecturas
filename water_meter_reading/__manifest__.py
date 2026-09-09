{
    'name': 'Water Meter Readings',
    'version': '19.0.4.1.0',
    'summary': 'Registro de lecturas de contadores de agua',
    'category': 'Tools',
    'author': 'Toni',
    'license': 'LGPL-3',
    'depends': ['base', 'mail'],
    'external_dependencies': {'python': ['openpyxl']},
    'assets': {
        'web.assets_backend': [
            'water_meter_reading/static/src/js/camera_image_field.js',
            'water_meter_reading/static/src/xml/camera_image_field.xml',
            'water_meter_reading/static/src/scss/mobile_reading.scss',
        ],
    },
    'data': [
        'security/groups.xml',
        'security/ir.model.access.csv',
        'views/res_users_views.xml',
        'views/water_meter_views.xml',
        'views/mobile_reading_views.xml',
        'views/water_period_views.xml',
        'views/meter_import_views.xml',
        'data/sequence_data.xml',
    ],
    'installable': True,
    'application': True,
}
