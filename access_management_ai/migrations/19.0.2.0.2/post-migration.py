# Copyright (C) NexGen Solutions


def migrate(cr, version):
    """Normalize AI provider model ids to currently valid API names."""
    replacements = {
        'access_management_ai.gemini_model': {
            'gemini-3.6-pro': 'gemini-3.6-flash',
            'gemini-3.5-pro': 'gemini-3.1-pro-preview',
            'gemini-3.5-flash-cyber': 'gemini-3.5-flash',
            'gemini-3.1-ultra': 'gemini-3.1-pro-preview',
            'gemini-3.1-pro': 'gemini-3.1-pro-preview',
            'gemini-2.0-pro': 'gemini-2.5-pro',
            'gemini-1.5-pro-latest': 'gemini-pro-latest',
            'gemini-1.5-pro': 'gemini-pro-latest',
            'gemini-1.5-flash': 'gemini-flash-latest',
            'gemini-1.5-flash-8b': 'gemini-flash-lite-latest',
            'gemini-1.0-pro': 'gemini-pro-latest',
            'gemini-pro': 'gemini-pro-latest',
            'gemini-2.5-flash': 'gemini-flash-latest',
            'gemini-2.5-flash-lite': 'gemini-flash-lite-latest',
        },
        'access_management_ai.claude_model': {
            'claude-5-fable': 'claude-fable-5',
            'claude-5-opus': 'claude-opus-5',
            'claude-5-sonnet': 'claude-sonnet-5',
            'claude-3-5-sonnet-latest': 'claude-sonnet-4-5',
            'claude-3-5-haiku-latest': 'claude-haiku-4-5',
            'claude-3-opus-latest': 'claude-opus-4-5',
            'claude-3-sonnet-20240229': 'claude-sonnet-4-5',
            'claude-3-haiku-20240307': 'claude-haiku-4-5',
        },
        'access_management_ai.openai_model': {
            'gpt-5.5-thinking': 'gpt-5.5',
            'gpt-5.5-instant': 'gpt-5.6-luna',
            'o1-preview': 'gpt-5.6-sol',
            'o1-mini': 'gpt-5.6-luna',
            'gpt-4-turbo': 'gpt-4.1',
            'gpt-4': 'gpt-4.1',
            'gpt-3.5-turbo': 'gpt-4o-mini',
        },
        'access_management_ai.cursor_model': {
            'claude-5-opus': 'claude-opus-5',
            'claude-5-sonnet': 'claude-sonnet-5',
            'gemini-3.6-flash': 'gpt-4o-mini',
            'gemini-3.1-ultra': 'gpt-4o-mini',
            'grok-4': 'grok-3',
            'deepseek-v4': 'deepseek-chat',
            'custom': 'gpt-4o-mini',
        },
    }
    for key, mapping in replacements.items():
        for old, new in mapping.items():
            cr.execute(
                """
                UPDATE ir_config_parameter
                   SET value = %s
                 WHERE key = %s
                   AND value = %s
                """,
                (new, key, old),
            )

    # Replace non-working default Cursor/custom endpoint URL
    cr.execute(
        """
        UPDATE ir_config_parameter
           SET value = 'https://api.openai.com/v1/chat/completions'
         WHERE key = 'access_management_ai.cursor_base_url'
           AND value LIKE '%%api.cursor.sh%%'
        """
    )
