# Copyright (C) NexGen Solutions


def migrate(cr, version):
    """Stop sending Cursor keys to OpenAI by clearing mistaken default URL."""
    cr.execute(
        """
        UPDATE ir_config_parameter
           SET value = ''
         WHERE key = 'access_management_ai.cursor_base_url'
           AND (
                value ILIKE '%%api.openai.com%%'
                OR value ILIKE '%%api.cursor.sh%%'
           )
        """
    )
