# Copyright (C) NexGen Solutions
import json
import os


def migrate(cr, version):
    """Seed full Cursor model catalog for dynamic Selection dropdown."""
    catalog_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        'models',
        'cursor_models_catalog.py',
    )
    namespace = {}
    with open(catalog_path, 'r', encoding='utf-8') as handle:
        exec(compile(handle.read(), catalog_path, 'exec'), namespace)
    catalog = namespace.get('CURSOR_MODEL_CATALOG') or []
    payload = json.dumps([{'id': mid, 'name': name} for mid, name in catalog])

    cr.execute(
        "SELECT id FROM ir_config_parameter WHERE key = %s",
        ('access_management_ai.cursor_models_json',),
    )
    row = cr.fetchone()
    if row:
        cr.execute(
            """
            UPDATE ir_config_parameter
               SET value = %s,
                   write_uid = 1,
                   write_date = (NOW() AT TIME ZONE 'UTC')
             WHERE id = %s
            """,
            (payload, row[0]),
        )
    else:
        cr.execute(
            """
            INSERT INTO ir_config_parameter
                (key, value, create_uid, write_uid, create_date, write_date)
            VALUES
                (%s, %s, 1, 1, NOW() AT TIME ZONE 'UTC', NOW() AT TIME ZONE 'UTC')
            """,
            ('access_management_ai.cursor_models_json', payload),
        )

    cr.execute(
        """
        UPDATE ir_config_parameter
           SET value = 'composer-2.5'
         WHERE key = 'access_management_ai.cursor_model'
           AND value IN (
                'gpt-5.5', 'gpt-4o-mini', 'gpt-4o', 'custom', 'grok-4', 'deepseek-v4',
                'claude-5-opus', 'claude-5-sonnet', 'gemini-3.6-flash', 'gemini-3.1-ultra'
           )
        """
    )
