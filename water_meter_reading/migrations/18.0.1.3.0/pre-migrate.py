def migrate(cr, version):
    """Add period_id column to water_reading if not exists (added in 1.2.0)."""
    cr.execute("""
        ALTER TABLE water_reading
        ADD COLUMN IF NOT EXISTS period_id INTEGER;
    """)
