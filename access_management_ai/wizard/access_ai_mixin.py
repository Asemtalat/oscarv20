# Copyright (C) NexGen Solutions
"""Shared AI provider calling for Generate-with-AI wizards."""
from odoo import api, models, _
from odoo.exceptions import AccessError, UserError
import json
import re
import urllib.error
import urllib.request


class AccessAiWizardMixin(models.AbstractModel):
    _name = 'access.ai.wizard.mixin'
    _description = 'Access Management AI Wizard Mixin'

    def _call_ai(self, full_prompt):
        """Call the configured AI provider and return raw text."""
        self.ensure_one()
        if not self.env.su and not self.env.user.has_group('access_management_ai.group_access_manager'):
            raise AccessError(_("Only Access Administrators can generate access settings with AI."))
        consent = self.env['ir.config_parameter'].sudo().get_bool(
            'access_management_ai.ai_data_consent', False
        )
        if not consent:
            raise UserError(_("Enable Allow AI Data Transmission in Settings before generating with AI."))
        provider = self.env['ir.config_parameter'].sudo().get_str(
            'access_management_ai.ai_provider', 'gemini'
        )
        text_response = ''

        try:
            if provider == 'gemini':
                api_key = self.env['ir.config_parameter'].sudo().get_str('access_management_ai.gemini_api_key')
                api_model_name = self.env['ir.config_parameter'].sudo().get_str(
                    'access_management_ai.gemini_model', 'gemini-flash-lite-latest'
                )
                gemini_model_map = {
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
                }
                api_model_name = gemini_model_map.get(api_model_name, api_model_name)
                if not api_key:
                    raise UserError(_("Please configure your Gemini API Key in Settings."))

                url = (
                    f"https://generativelanguage.googleapis.com/v1beta/models/"
                    f"{api_model_name}:generateContent?key={api_key}"
                )
                data = {
                    "contents": [{"parts": [{"text": full_prompt}]}],
                    "generationConfig": {
                        "temperature": 0.2,
                        "maxOutputTokens": 8192,
                        "responseMimeType": "application/json",
                    },
                }
                req = urllib.request.Request(
                    url,
                    data=json.dumps(data).encode('utf-8'),
                    headers={'Content-Type': 'application/json'},
                )
                with urllib.request.urlopen(req, timeout=90) as response:
                    res = json.loads(response.read().decode('utf-8'))
                    parts = (
                        res.get('candidates', [{}])[0]
                        .get('content', {})
                        .get('parts', [])
                    )
                    text_response = ''.join(p.get('text', '') for p in parts)

            elif provider == 'claude':
                api_key = self.env['ir.config_parameter'].sudo().get_str('access_management_ai.claude_api_key')
                model_name = self.env['ir.config_parameter'].sudo().get_str(
                    'access_management_ai.claude_model', 'claude-sonnet-5'
                )
                claude_model_map = {
                    'claude-5-fable': 'claude-fable-5',
                    'claude-5-opus': 'claude-opus-5',
                    'claude-5-sonnet': 'claude-sonnet-5',
                    'claude-3-5-sonnet-latest': 'claude-sonnet-4-5',
                    'claude-3-5-haiku-latest': 'claude-haiku-4-5',
                    'claude-3-opus-latest': 'claude-opus-4-5',
                    'claude-3-sonnet-20240229': 'claude-sonnet-4-5',
                    'claude-3-haiku-20240307': 'claude-haiku-4-5',
                }
                model_name = claude_model_map.get(model_name, model_name)
                if not api_key:
                    raise UserError(_("Please configure your Claude API Key in Settings."))

                url = "https://api.anthropic.com/v1/messages"
                data = {
                    "model": model_name,
                    "max_tokens": 4096,
                    "messages": [{"role": "user", "content": full_prompt}],
                }
                headers = {
                    'x-api-key': api_key,
                    'anthropic-version': '2023-06-01',
                    'content-type': 'application/json',
                }
                req = urllib.request.Request(
                    url, data=json.dumps(data).encode('utf-8'), headers=headers
                )
                with urllib.request.urlopen(req, timeout=90) as response:
                    res = json.loads(response.read().decode('utf-8'))
                    text_response = res.get('content', [{}])[0].get('text', '')

            elif provider == 'openai':
                api_key = self.env['ir.config_parameter'].sudo().get_str(
                    'access_management_ai.openai_api_key'
                )
                model = self.env['ir.config_parameter'].sudo().get_str(
                    'access_management_ai.openai_model', 'gpt-5.6-terra'
                )
                openai_model_map = {
                    'gpt-5.5-thinking': 'gpt-5.5',
                    'gpt-5.5-instant': 'gpt-5.6-luna',
                    'o1-preview': 'gpt-5.6-sol',
                    'o1-mini': 'gpt-5.6-luna',
                    'gpt-4-turbo': 'gpt-4.1',
                    'gpt-4': 'gpt-4.1',
                    'gpt-3.5-turbo': 'gpt-4o-mini',
                }
                model = openai_model_map.get(model, model)
                if not api_key:
                    raise UserError(_("Please configure your OpenAI API Key in Settings."))
                from odoo.addons.access_management_ai.models.ai_provider_cursor import openai_compatible_chat
                text_response = openai_compatible_chat(
                    api_key,
                    "https://api.openai.com/v1/chat/completions",
                    model,
                    full_prompt,
                    timeout=90,
                    json_mode=True,
                )

            elif provider == 'cursor':
                api_key = self.env['ir.config_parameter'].sudo().get_str(
                    'access_management_ai.cursor_api_key'
                )
                model = self.env['ir.config_parameter'].sudo().get_str(
                    'access_management_ai.cursor_model', 'composer-2.5'
                )
                cursor_model_map = {
                    'claude-5-opus': 'claude-opus-5-medium',
                    'claude-5-sonnet': 'claude-sonnet-5-medium',
                    'gemini-3.6-flash': 'composer-2.5',
                    'gemini-3.1-ultra': 'composer-2.5',
                    'grok-4': 'cursor-grok-4.5-medium',
                    'deepseek-v4': 'composer-2.5',
                    'custom': 'composer-2.5',
                    'gpt-5.5': 'gpt-5.5-medium',
                    'gpt-4o-mini': 'composer-2.5',
                    'gpt-4o': 'composer-2.5',
                }
                model = cursor_model_map.get(model, model)
                base_url = (
                    self.env['ir.config_parameter'].sudo().get_str(
                        'access_management_ai.cursor_base_url', ''
                    )
                    or ''
                ).strip()
                from odoo.addons.access_management_ai.models import ai_provider_cursor as cursor_ai
                if not api_key:
                    raise UserError(_("Please configure your Cursor API Key in Settings."))
                if not base_url or cursor_ai.is_openai_chat_url(base_url):
                    text_response = cursor_ai.cursor_generate_text(
                        api_key, model, full_prompt, timeout=180
                    )
                else:
                    text_response = cursor_ai.openai_compatible_chat(
                        api_key,
                        base_url,
                        model,
                        full_prompt,
                        timeout=90,
                        json_mode=True,
                    )
            else:
                raise UserError(_("Unsupported AI provider: %s") % provider)

        except urllib.error.HTTPError as e:
            error_msg = e.read().decode('utf-8', errors='replace')
            raise UserError(
                _("API Error from %s: %s\n\nDetails: %s")
                % (provider.capitalize(), e.reason, error_msg)
            )
        except UserError:
            raise
        except Exception as e:
            raise UserError(_("Error communicating with AI Provider: %s") % str(e))

        return text_response or ''

    @api.model
    def _extract_json(self, text_response):
        """Strip markdown fences / surrounding text and parse JSON."""
        text = (text_response or '').strip()
        if not text:
            raise UserError(_("AI returned an empty response."))

        fence = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text, flags=re.IGNORECASE)
        if fence:
            text = fence.group(1).strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find('{')
            end = text.rfind('}')
            if start >= 0 and end > start:
                try:
                    return json.loads(text[start:end + 1])
                except json.JSONDecodeError:
                    pass
            raise UserError(_("AI returned invalid JSON.\n\nRaw Response: %s") % text_response)
