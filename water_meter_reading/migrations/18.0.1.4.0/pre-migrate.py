def migrate(cr, version):
    """Add can_edit_readings column to res_users if not exists."""
    cr.execute("""
        ALTER TABLE res_users
        ADD COLUMN IF NOT EXISTS can_edit_readings BOOLEAN DEFAULT FALSE;
    """)
