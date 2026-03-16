def migrate(cr, version):
    """Convert reading columns from float to integer."""
    for col in ('reading_previous', 'reading_current', 'difference'):
        cr.execute(
            f"ALTER TABLE water_reading "
            f"ALTER COLUMN {col} TYPE integer USING ROUND({col})::integer"
        )
