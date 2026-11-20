# Copyright (C) NexGen Solutions
"""Native Cursor AI helpers (Cursor API key / agent CLI).

Cursor does NOT provide an OpenAI-compatible /v1/chat/completions endpoint.
Keys starting with ``crsr_`` must talk to api.cursor.com (or the local agent CLI),
never to api.openai.com.
"""
from odoo.exceptions import UserError
from odoo import _

import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request

_logger = logging.getLogger(__name__)

CURSOR_API_BASE = 'https://api.cursor.com'
OPENAI_CHAT_HINTS = (
    'api.openai.com',
    'openai.com/v1/chat',
)
_ANSI_RE = re.compile(r'\x1b\[[0-9;]*m')
_NOISE_RE = re.compile(
    r'(index\.js:\d+|</?html|</?script|open-browser|webpack|Stack trace:|'
    r'var c=n\(|function\(|=>|const m=)',
    re.IGNORECASE,
)


def _find_agent_bin():
    candidates = [
        shutil.which('agent'),
        shutil.which('cursor-agent'),
        '/home/synconics/.local/bin/agent',
        '/usr/local/bin/agent',
        os.path.expanduser('~/.local/bin/agent'),
    ]
    return next((path for path in candidates if path and os.path.isfile(path)), None)


def is_openai_chat_url(url):
    url = (url or '').strip().lower()
    return any(hint in url for hint in OPENAI_CHAT_HINTS)


def _strip_ansi(text):
    return _ANSI_RE.sub('', text or '')


def _looks_like_agent_dump(text):
    text = text or ''
    if 'index.js:' in text or '</html>' in text or 'open-browser.ts' in text:
        return True
    if len(text) > 300 and _NOISE_RE.search(text[:500]):
        return True
    return False


def _sanitize_agent_message(text, limit=600):
    """Keep only human-readable agent CLI lines; drop minified JS / HTML dumps."""
    text = _strip_ansi(text or '')
    if not text:
        return ''
    if 'WebAssembly.instantiate' in text or 'Cannot allocate Wasm memory' in text:
        return _(
            "Cursor Agent ran out of virtual memory (WebAssembly). "
            "Odoo’s memory limit was blocking the Agent CLI; retry after upgrade, "
            "or raise --limit-memory-soft / soft RLIMIT_AS on the Odoo process."
        )[:limit]
    if _looks_like_agent_dump(text):
        # Extract any short warning lines if present
        warnings = []
        for line in text.splitlines():
            line = line.strip()
            if not line or _looks_like_agent_dump(line) or len(line) > 200:
                continue
            if any(k in line.lower() for k in ('warning', 'error', 'invalid', 'failed', 'unauthorized', 'rangeerror')):
                warnings.append(line)
        if warnings:
            return '\n'.join(warnings)[:limit]
        return _(
            "Cursor Agent CLI crashed while starting (internal debug dump suppressed). "
            "Ensure the `agent` CLI works in a terminal with your Cursor API key."
        )[:limit]

    lines = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if _NOISE_RE.search(line):
            continue
        if len(line) > 400:
            continue
        lines.append(line)
    cleaned = '\n'.join(lines).strip()
    return (cleaned or _('No readable details from Cursor Agent CLI.'))[:limit]


def cursor_validate_api_key(api_key):
    """Validate a Cursor API key via GET /v1/me. Returns a short status string."""
    if not api_key:
        raise UserError(_("Please set the Cursor API Key first."))
    req = urllib.request.Request(
        f'{CURSOR_API_BASE}/v1/me',
        headers={
            'Authorization': f'Bearer {api_key}',
            'Accept': 'application/json',
            'User-Agent': 'odoo-access-management',
        },
        method='GET',
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        details = e.read().decode('utf-8', errors='replace')
        raise UserError(
            _("Cursor API key rejected (%s).\n\nDetails: %s\n\n"
              "Create/manage keys at https://cursor.com/dashboard/api "
              "(not platform.openai.com).")
            % (e.code, _sanitize_agent_message(details, 400))
        )
    except Exception as e:
        raise UserError(_("Could not reach Cursor API: %s") % str(e))

    name = (
        data.get('apiKeyName')
        or data.get('userEmail')
        or data.get('email')
        or data.get('userFirstName')
        or 'OK'
    )
    return _('Authenticated as %s') % name


def _unlimit_child_address_space():
    """Raise RLIMIT_AS in the forked child before exec.

    Odoo sets a soft virtual-memory cap (``limit_memory_soft``, often ~2.5GB).
    Nested Cursor Agent (Node + Wasm) inherits that cap and crashes with
    ``WebAssembly.instantiate(): Out of memory``. Hard limit is usually
    unlimited, so the child can safely raise the soft limit.
    """
    try:
        import resource
        for name in ('RLIMIT_AS', 'RLIMIT_DATA', 'RLIMIT_RSS'):
            lim = getattr(resource, name, None)
            if lim is None:
                continue
            soft, hard = resource.getrlimit(lim)
            # Prefer unlimited when the hard limit allows it.
            target = hard if hard != resource.RLIM_INFINITY else resource.RLIM_INFINITY
            if soft == target:
                continue
            try:
                resource.setrlimit(lim, (target, hard))
            except (ValueError, OSError):
                if hard != resource.RLIM_INFINITY:
                    try:
                        resource.setrlimit(lim, (hard, hard))
                    except (ValueError, OSError):
                        pass
    except Exception:
        pass


def cursor_generate_text(api_key, model, prompt, timeout=180):
    """Run a one-shot Cursor Agent ask/print call and return assistant text.

    Uses the official Cursor agent CLI with ``CURSOR_API_KEY``. This is the
    supported way to get model output for a ``crsr_`` key. Cloud Agents API
    is repo/coding oriented and is not a chat-completions API.
    """
    if not api_key:
        raise UserError(_("Please configure your Cursor API Key in Settings."))

    agent_bin = _find_agent_bin()
    if not agent_bin:
        raise UserError(
            _("Cursor Agent CLI was not found on this server.\n"
              "Install the Cursor CLI (`agent`) or set a custom OpenAI-compatible "
              "proxy URL that accepts Cursor traffic.\n\n"
              "Note: https://api.openai.com does not accept Cursor API keys "
              "(crsr_…).")
        )

    # Quick auth check first — clearer errors than agent CLI dumps
    cursor_validate_api_key(api_key)

    model = model or 'composer-2.5'
    home = os.path.expanduser('~')
    local_bin = os.path.expanduser('~/.local/bin')
    agent_dir = os.path.dirname(os.path.realpath(agent_bin))
    # Build a clean env — inheriting the Odoo/Cursor-IDE process env makes the
    # nested `agent` CLI crash and dump index.js/HTML onto stderr.
    env = {
        'HOME': home,
        'USER': os.environ.get('USER', ''),
        'LOGNAME': os.environ.get('LOGNAME', os.environ.get('USER', '')),
        'PATH': f"{local_bin}:{agent_dir}:/usr/local/bin:/usr/bin:/bin",
        'LANG': os.environ.get('LANG', 'C.UTF-8'),
        'LC_ALL': os.environ.get('LC_ALL', os.environ.get('LANG', 'C.UTF-8')),
        'TERM': 'dumb',
        'CI': '1',
        'NO_BROWSER': '1',
        'BROWSER': 'true',
        'CURSOR_API_KEY': api_key,
        'CURSOR_AGENT_DISABLE_DEBUG_LOG': '1',
        'TMPDIR': tempfile.gettempdir(),
        'XDG_CACHE_HOME': os.environ.get('XDG_CACHE_HOME', os.path.join(home, '.cache')),
        'XDG_CONFIG_HOME': os.environ.get('XDG_CONFIG_HOME', os.path.join(home, '.config')),
    }
    # Optional SSL certs if present on the host
    for key in ('SSL_CERT_FILE', 'SSL_CERT_DIR', 'REQUESTS_CA_BUNDLE', 'CURL_CA_BUNDLE'):
        if os.environ.get(key):
            env[key] = os.environ[key]

    with tempfile.TemporaryDirectory(prefix='am-cursor-') as workspace:
        prompt_path = os.path.join(workspace, 'prompt.txt')
        with open(prompt_path, 'w', encoding='utf-8') as handle:
            handle.write(prompt)

        out_path = os.path.join(workspace, 'agent.out')
        err_path = os.path.join(workspace, 'agent.err')
        # Wrap via bash so we can raise ulimit without preexec_fn (unsafe in
        # threaded Odoo workers). Odoo's soft RLIMIT_AS (~2.5GB) is inherited
        # by Node and causes Wasm OOM on Agent startup.
        cmd = [
            'bash', '--noprofile', '--norc', '-c',
            'ulimit -v unlimited 2>/dev/null || true; '
            'ulimit -d unlimited 2>/dev/null || true; '
            'exec "$@"',
            'am-cursor-agent',
            agent_bin,
            '--print',
            '--mode', 'ask',
            '--output-format', 'text',
            '--trust',
            '--sandbox', 'disabled',
            '--workspace', workspace,
            '--model', model,
            prompt,
        ]
        try:
            with open(out_path, 'w', encoding='utf-8') as out_f, open(err_path, 'w', encoding='utf-8') as err_f:
                completed = subprocess.run(
                    cmd,
                    stdin=subprocess.DEVNULL,
                    stdout=out_f,
                    stderr=err_f,
                    timeout=timeout,
                    check=False,
                    env=env,
                    cwd=workspace,
                    start_new_session=True,
                    close_fds=True,
                )
            with open(out_path, 'r', encoding='utf-8', errors='replace') as out_f:
                stdout_data = out_f.read()
            with open(err_path, 'r', encoding='utf-8', errors='replace') as err_f:
                stderr_data = err_f.read()
            # Mimic CompletedProcess fields used below
            class _Result:
                pass
            completed_result = _Result()
            completed_result.returncode = completed.returncode
            completed_result.stdout = stdout_data
            completed_result.stderr = stderr_data
            completed = completed_result
        except subprocess.TimeoutExpired:
            raise UserError(_("Cursor Agent timed out after %s seconds.") % timeout)
        except OSError as e:
            raise UserError(_("Failed to start Cursor Agent CLI: %s") % str(e))

    stdout = (completed.stdout or '').strip()
    stderr_clean = _sanitize_agent_message(completed.stderr or '')

    combined_lower = f'{stderr_clean}\n{_strip_ansi(completed.stderr or "")}\n{stdout}'.lower()
    if 'api key is invalid' in combined_lower or 'invalid api key' in combined_lower:
        raise UserError(
            _("Cursor API key is invalid for the Agent CLI.\n\n%s\n\n"
              "Create a key at https://cursor.com/dashboard/api")
            % (stderr_clean or _('Unauthorized'))
        )

    if completed.returncode != 0 and not stdout:
        raise UserError(
            _("Cursor Agent failed (exit %s).\n\n%s")
            % (completed.returncode, stderr_clean)
        )
    if not stdout:
        raise UserError(
            _("Cursor Agent returned an empty response.\n\n%s") % (stderr_clean or '')
        )
    if _looks_like_agent_dump(stdout) and 'profiles' not in stdout.lower():
        raise UserError(
            _("Cursor Agent returned an unusable debug dump instead of model output.\n"
              "Try model composer-2.5, or re-check the API key.\n\n%s")
            % stderr_clean
        )
    return stdout


def openai_compatible_chat(api_key, base_url, model, prompt, timeout=90, json_mode=False):
    """Call a true OpenAI-compatible /chat/completions endpoint."""
    if not api_key:
        raise UserError(_("Please set the API Key first."))
    if not base_url:
        raise UserError(_("Please set the chat completions URL first."))
    if is_openai_chat_url(base_url) and (api_key or '').startswith('crsr_'):
        raise UserError(
            _("Your Cursor API key (crsr_…) cannot be used with OpenAI "
              "(api.openai.com).\n\n"
              "Leave the Chat Completions URL empty to use native Cursor Agent, "
              "or point it at an OpenAI-compatible proxy that accepts Cursor keys.\n"
              "Cursor keys: https://cursor.com/dashboard/api")
        )

    data = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
    }
    if json_mode:
        data["response_format"] = {"type": "json_object"}
    req = urllib.request.Request(
        base_url,
        data=json.dumps(data).encode('utf-8'),
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            res = json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        details = e.read().decode('utf-8', errors='replace')
        raise UserError(
            _("API Error from custom endpoint: %s\n\nDetails: %s")
            % (e.reason, _sanitize_agent_message(details, 500))
        )
    return (
        res.get('choices', [{}])[0].get('message', {}).get('content') or ''
    ).strip()
