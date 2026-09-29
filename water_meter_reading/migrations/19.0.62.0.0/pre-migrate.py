def migrate(cr, version):
    """Keep one reading per meter and period before creating the unique index."""
    cr.execute(
        """
        WITH ranked AS (
            SELECT
                id,
                ROW_NUMBER() OVER (
                    PARTITION BY meter_id, period_id
                    ORDER BY
                        CASE WHEN estimated_reading THEN 1 ELSE 0 END,
                        CASE WHEN reading_current > 0 THEN 0 ELSE 1 END,
                        write_date DESC NULLS LAST,
                        create_date DESC NULLS LAST,
                        id DESC
                ) AS row_number
            FROM water_reading
            WHERE meter_id IS NOT NULL AND period_id IS NOT NULL
        )
        DELETE FROM water_reading AS duplicate
        USING ranked
        WHERE duplicate.id = ranked.id
          AND ranked.row_number > 1
        """
    )
