# Copyright (C) NexGen Solutions
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import json
import logging
import os
import shutil
import subprocess
import urllib.error
import urllib.request

from .cursor_models_catalog import CURSOR_MODEL_CATALOG
from . import ai_provider_cursor as cursor_ai

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    def execute(self):
        self.ensure_one()
        modules = self.env['ir.module.module']
        if modules._access_management_module_change_blocked():
            # Reject module changes before execute persists unrelated settings
            # or opens an uninstall dialog. Ordinary settings remain editable.
            classified = self.with_context(active_test=False)._get_classified_fields()
            changes = classified['module'].filtered(lambda module:
                (self[f'module_{module.name}'] and module.state != 'installed') or
                (not self[f'module_{module.name}'] and module.state in ('installed', 'to upgrade')))
            if changes:
                modules._access_management_module_change_allowed()
        return super().execute()

    am_ai_provider = fields.Selection([
        ('gemini', 'Google Gemini'),
        ('claude', 'Anthropic Claude'),
        ('openai', 'OpenAI'),
        ('cursor', 'Cursor AI'),
    ], string="AI Provider", config_parameter="access_management_ai.ai_provider", default='gemini')

    am_ai_data_consent = fields.Boolean(
        string="Allow AI Data Transmission",
        config_parameter="access_management_ai.ai_data_consent",
        help="Allow administrator prompts and access-rule or role schemas to be sent to the selected external AI provider.",
    )

    am_gemini_api_key = fields.Char("Gemini API Key", config_parameter="access_management_ai.gemini_api_key")
    am_gemini_model = fields.Selection([
        ('gemini-flash-latest', 'Gemini Flash (Latest alias)'),
        ('gemini-flash-lite-latest', 'Gemini Flash-Lite (Latest alias)'),
        ('gemini-pro-latest', 'Gemini Pro (Latest alias)'),
        ('gemini-3.6-flash', 'Gemini 3.6 Flash'),
        ('gemini-3.5-flash', 'Gemini 3.5 Flash'),
        ('gemini-3.5-flash-lite', 'Gemini 3.5 Flash-Lite'),
        ('gemini-3.1-pro-preview', 'Gemini 3.1 Pro (Preview)'),
        ('gemini-3.1-flash-lite', 'Gemini 3.1 Flash-Lite'),
        ('gemini-3-pro-preview', 'Gemini 3 Pro (Preview)'),
        ('gemini-3-flash-preview', 'Gemini 3 Flash (Preview)'),
        ('gemini-2.5-pro', 'Gemini 2.5 Pro'),
    ], string="Gemini Model", config_parameter="access_management_ai.gemini_model",
       default='gemini-flash-lite-latest')

    am_claude_api_key = fields.Char("Claude API Key", config_parameter="access_management_ai.claude_api_key")
    am_claude_model = fields.Selection([
        ('claude-fable-5', 'Claude Fable 5 (Highest Capability)'),
        ('claude-opus-5', 'Claude Opus 5'),
        ('claude-sonnet-5', 'Claude Sonnet 5'),
        ('claude-haiku-4-5', 'Claude Haiku 4.5 (Fast)'),
        ('claude-opus-4-8', 'Claude Opus 4.8'),
        ('claude-opus-4-7', 'Claude Opus 4.7'),
        ('claude-opus-4-6', 'Claude Opus 4.6'),
        ('claude-sonnet-4-6', 'Claude Sonnet 4.6'),
        ('claude-sonnet-4-5', 'Claude Sonnet 4.5'),
        ('claude-opus-4-5', 'Claude Opus 4.5'),
    ], string="Claude Model", config_parameter="access_management_ai.claude_model",
       default='claude-sonnet-5')

    am_openai_api_key = fields.Char("OpenAI API Key", config_parameter="access_management_ai.openai_api_key")
    am_openai_model = fields.Selection([
        ('gpt-5.6', 'GPT-5.6 (alias → Sol)'),
        ('gpt-5.6-sol', 'GPT-5.6 Sol (Flagship)'),
        ('gpt-5.6-terra', 'GPT-5.6 Terra (Balanced)'),
        ('gpt-5.6-luna', 'GPT-5.6 Luna (Fast / Cost)'),
        ('gpt-5.5', 'GPT-5.5'),
        ('gpt-5.5-pro', 'GPT-5.5 Pro'),
        ('gpt-4.1', 'GPT-4.1'),
        ('gpt-4.1-mini', 'GPT-4.1 Mini'),
        ('gpt-4o', 'GPT-4o'),
        ('gpt-4o-mini', 'GPT-4o Mini'),
    ], string="OpenAI Model", config_parameter="access_management_ai.openai_model",
       default='gpt-5.6-terra')

    am_cursor_api_key = fields.Char(
        "Cursor API Key",
        config_parameter="access_management_ai.cursor_api_key",
        help="Cursor API key (crsr_…) from https://cursor.com/dashboard/api — not an OpenAI key.",
    )
    am_cursor_base_url = fields.Char(
        "Optional OpenAI-Compatible Proxy URL",
        config_parameter="access_management_ai.cursor_base_url",
        default=False,
        help="Leave empty to use native Cursor Agent with your crsr_ key. "
             "Only set this if you run a proxy that speaks /v1/chat/completions. "
             "Do NOT use https://api.openai.com — it rejects Cursor keys.",
    )
    am_cursor_model = fields.Selection(
        selection='_selection_cursor_models',
        string="Cursor Model",
        config_parameter="access_management_ai.cursor_model",
        default='composer-2.5',
        help="Dynamically loaded from Cursor. Use Refresh Cursor Models to update the list.",
    )
    am_cursor_models_count = fields.Integer(
        string="Cursor Models Loaded",
        compute='_compute_cursor_models_count',
    )

    @api.model
    def _am_cursor_fallback_selection(self):
        return list(CURSOR_MODEL_CATALOG)

    @api.model
    def _am_get_cached_cursor_models(self):
        raw = self.env['ir.config_parameter'].sudo().get_str(
            'access_management_ai.cursor_models_json', ''
        )
        if not raw:
            return []
        try:
            data = json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            return []
        result = []
        for item in data or []:
            if isinstance(item, dict) and item.get('id'):
                result.append((item['id'], item.get('name') or item['id']))
            elif isinstance(item, (list, tuple)) and item:
                result.append((item[0], item[1] if len(item) > 1 else item[0]))
        return result

    @api.model
    def _selection_cursor_models(self):
        cached = self._am_get_cached_cursor_models()
        selection = cached or self._am_cursor_fallback_selection()
        # Ensure currently configured value remains selectable
        current = self.env['ir.config_parameter'].sudo().get_str(
            'access_management_ai.cursor_model', ''
        )
        ids = {m[0] for m in selection}
        if current and current not in ids:
            selection = [(current, current)] + selection
        return selection

    @api.depends_context('uid')
    def _compute_cursor_models_count(self):
        count = len(self._selection_cursor_models())
        for rec in self:
            rec.am_cursor_models_count = count

    @api.model
    def _am_fetch_cursor_models_from_api(self, api_key):
        """Fetch models from Cursor Cloud API GET /v1/models."""
        if not api_key:
            return []
        req = urllib.request.Request(
            'https://api.cursor.com/v1/models',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Accept': 'application/json',
                'User-Agent': 'odoo-access-management',
            },
            method='GET',
        )
        with urllib.request.urlopen(req, timeout=45) as response:
            payload = json.loads(response.read().decode('utf-8'))
        items = []
        raw_items = payload if isinstance(payload, list) else (
            payload.get('items') or payload.get('data') or payload.get('models') or [])
        for entry in raw_items:
            if isinstance(entry, str):
                items.append({'id': entry, 'name': entry})
                continue
            if not isinstance(entry, dict):
                continue
            model_id = entry.get('id') or (entry.get('model') or {}).get('id')
            if not model_id:
                continue
            name = (
                entry.get('displayName')
                or entry.get('display_name')
                or entry.get('name')
                or model_id
            )
            items.append({'id': model_id, 'name': name})
            for alias in entry.get('aliases') or []:
                if alias and alias != model_id:
                    items.append({'id': alias, 'name': f"{name} ({alias})"})
            for variant in entry.get('variants') or []:
                # Variants are params overlays; keep base id only unless labeled
                label = variant.get('displayName')
                if label and model_id:
                    items.append({'id': model_id, 'name': f"{name} / {label}"})
        return items

    @api.model
    def _am_fetch_cursor_models_from_cli(self):
        """Fallback: parse `agent --list-models` when Cursor CLI is installed."""
        candidates = [
            shutil.which('agent'),
            shutil.which('cursor-agent'),
            '/home/synconics/.local/bin/agent',
            '/usr/local/bin/agent',
            os.path.expanduser('~/.local/bin/agent'),
        ]
        agent_bin = next((path for path in candidates if path and os.path.isfile(path)), None)
        if not agent_bin:
            return []
        try:
            env = dict(os.environ)
            env.setdefault('HOME', os.path.expanduser('~'))
            local_bin = os.path.expanduser('~/.local/bin')
            env['PATH'] = f"{local_bin}:{env.get('PATH', '')}"
            completed = subprocess.run(
                [agent_bin, '--list-models'],
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
                env=env,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            _logger.info("Cursor CLI model list failed: %s", exc)
            return []
        if completed.returncode not in (0, None) and not (completed.stdout or '').strip():
            _logger.info(
                "Cursor CLI model list exit=%s stderr=%s",
                completed.returncode,
                (completed.stderr or '')[:300],
            )
            return []
        items = []
        seen = set()
        for line in (completed.stdout or '').splitlines():
            line = line.strip()
            if ' - ' not in line:
                continue
            model_id, label = line.split(' - ', 1)
            model_id = model_id.strip()
            label = label.strip()
            if not model_id or model_id.lower() in ('available models',) or model_id in seen:
                continue
            # Skip help/usage noise
            if ' ' in model_id:
                continue
            seen.add(model_id)
            items.append({'id': model_id, 'name': label or model_id})
        return items

    def action_refresh_cursor_models(self):
        """Refresh Cursor model dropdown from API (preferred) or local CLI."""
        self.ensure_one()
        api_key = self.am_cursor_api_key or self.env['ir.config_parameter'].sudo().get_str(
            'access_management_ai.cursor_api_key'
        )
        source = None
        items = []
        errors = []

        if api_key:
            try:
                items = self._am_fetch_cursor_models_from_api(api_key)
                source = 'Cursor API'
            except urllib.error.HTTPError as e:
                details = e.read().decode('utf-8', errors='replace')
                errors.append(_("API %s: %s") % (e.code, details[:240]))
            except Exception as e:
                errors.append(str(e))

        if not items:
            try:
                items = self._am_fetch_cursor_models_from_cli()
                if items:
                    source = 'Cursor CLI'
            except Exception as e:
                errors.append(str(e))

        if not items:
            # Seed bundled catalog so the dropdown is never empty
            items = [{'id': mid, 'name': label} for mid, label in CURSOR_MODEL_CATALOG]
            source = 'bundled catalog'
            if errors:
                _logger.warning("Cursor model refresh fell back to catalog: %s", errors)

        # Deduplicate while preserving order
        seen = set()
        unique = []
        for item in items:
            mid = item['id']
            if mid in seen:
                continue
            seen.add(mid)
            unique.append({'id': mid, 'name': item.get('name') or mid})

        self.env['ir.config_parameter'].sudo().set_str(
            'access_management_ai.cursor_models_json',
            json.dumps(unique),
        )

        # Keep a valid selected model
        current = self.am_cursor_model or self.env['ir.config_parameter'].sudo().get_str(
            'access_management_ai.cursor_model'
        )
        ids = {m['id'] for m in unique}
        if current not in ids:
            preferred = 'composer-2.5' if 'composer-2.5' in ids else (unique[0]['id'] if unique else False)
            if preferred:
                self.am_cursor_model = preferred
                self.env['ir.config_parameter'].sudo().set_str(
                    'access_management_ai.cursor_model', preferred
                )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Cursor Models Updated'),
                'message': _('Loaded %s models from %s.') % (len(unique), source),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            },
        }

    def action_test_ai_connection(self):
        """Ping the configured provider/model with a tiny prompt."""
        self.ensure_one()
        if not self._am_ai_data_consent_granted():
            raise UserError(_("Enable Allow AI Data Transmission before contacting an AI provider."))
        provider = self.am_ai_provider or 'gemini'
        try:
            reply = self._am_test_provider(provider)
        except UserError:
            raise
        except urllib.error.HTTPError as e:
            details = e.read().decode('utf-8', errors='replace')
            raise UserError(
                _("API Error from %s: %s\n\nDetails: %s")
                % (provider.capitalize(), e.reason, details[:500])
            )
        except Exception as e:
            raise UserError(_("Connection test failed: %s") % str(e))
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('AI Connection OK'),
                'message': _('Provider "%s" responded: %s') % (provider, (reply or '')[:120]),
                'type': 'success',
                'sticky': False,
            },
        }

    def _am_ai_data_consent_granted(self):
        # Honor the current form value, including an unsaved opt-out.
        return bool(self.am_ai_data_consent)

    def _am_test_provider(self, provider):
        prompt = 'Reply with exactly: OK'
        if provider == 'gemini':
            api_key = self.am_gemini_api_key or self.env['ir.config_parameter'].sudo().get_str(
                'access_management_ai.gemini_api_key'
            )
            model = self.am_gemini_model or 'gemini-flash-lite-latest'
            if not api_key:
                raise UserError(_("Please set the Gemini API Key first."))
            url = (
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{model}:generateContent?key={api_key}"
            )
            data = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0, "maxOutputTokens": 256},
            }
            req = urllib.request.Request(
                url, data=json.dumps(data).encode('utf-8'),
                headers={'Content-Type': 'application/json'},
            )
            with urllib.request.urlopen(req, timeout=45) as response:
                res = json.loads(response.read().decode('utf-8'))
            parts = (
                res.get('candidates', [{}])[0]
                .get('content', {})
                .get('parts', [])
            )
            text = ''.join(p.get('text', '') for p in parts).strip()
            if not text:
                raise UserError(
                    _("Gemini model '%s' returned an empty response. "
                      "Try gemini-flash-lite-latest or gemini-3.5-flash-lite.")
                    % model
                )
            return text

        if provider == 'claude':
            api_key = self.am_claude_api_key or self.env['ir.config_parameter'].sudo().get_str(
                'access_management_ai.claude_api_key'
            )
            model = self.am_claude_model or 'claude-sonnet-5'
            if not api_key:
                raise UserError(_("Please set the Claude API Key first."))
            data = {
                "model": model,
                "max_tokens": 32,
                "messages": [{"role": "user", "content": prompt}],
            }
            req = urllib.request.Request(
                "https://api.anthropic.com/v1/messages",
                data=json.dumps(data).encode('utf-8'),
                headers={
                    'x-api-key': api_key,
                    'anthropic-version': '2023-06-01',
                    'content-type': 'application/json',
                },
            )
            with urllib.request.urlopen(req, timeout=45) as response:
                res = json.loads(response.read().decode('utf-8'))
            return (res.get('content', [{}])[0].get('text') or '').strip() or '(empty)'

        if provider == 'openai':
            api_key = self.am_openai_api_key or self.env['ir.config_parameter'].sudo().get_str(
                'access_management_ai.openai_api_key'
            )
            model = self.am_openai_model or 'gpt-5.6-terra'
            return cursor_ai.openai_compatible_chat(
                api_key,
                "https://api.openai.com/v1/chat/completions",
                model,
                prompt,
                timeout=45,
            )

        if provider == 'cursor':
            api_key = self.am_cursor_api_key or self.env['ir.config_parameter'].sudo().get_str(
                'access_management_ai.cursor_api_key'
            )
            model = (
                self.am_cursor_model
                or self.env['ir.config_parameter'].sudo().get_str(
                    'access_management_ai.cursor_model', 'composer-2.5'
                )
            )
            base_url = (
                self.am_cursor_base_url
                or self.env['ir.config_parameter'].sudo().get_str(
                    'access_management_ai.cursor_base_url', ''
                )
                or ''
            ).strip()
            # Native Cursor path (default): validate key against api.cursor.com
            if not base_url or cursor_ai.is_openai_chat_url(base_url):
                return cursor_ai.cursor_validate_api_key(api_key)
            return cursor_ai.openai_compatible_chat(
                api_key, base_url, model, prompt, timeout=45
            )

        raise UserError(_("Unsupported AI provider: %s") % provider)
