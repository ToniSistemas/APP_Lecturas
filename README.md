# APP_Lecturas

Aplicación Odoo para registro de lecturas de contadores de agua (módulo `water_meter_reading`).

Instalación rápida (desarrollo):

1. Coloca la carpeta `water_meter_reading` en el `addons_path` de tu instancia Odoo (o añade la raíz del repo al `addons_path`).
2. Reinicia el servidor Odoo.
3. Actualiza la lista de apps y busca *Water Meter Readings*; instala el módulo.

Notas:
- El módulo está en la rama `19.0` del repositorio.
- Las fotos se guardan como `Binary` en el modelo `water.reading.photo` (puedes adaptar almacenamiento a filesystem/S3).
- Ver `__manifest__.py` para dependencias.
