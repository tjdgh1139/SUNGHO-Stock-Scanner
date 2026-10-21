"""KIS OAuth token cache for an independent read-only collector.

Uses an exclusive flock across processes and atomic 0600 JSON replacement.
Never prints credentials or access tokens. Does not place orders.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
from datetime import datetime, timezone

import requests

TOKEN_URL = 'https://openapi.koreainvestment.com:9443/oauth2/tokenP'
DEFAULT_CACHE = '/opt/atlas/private/kis_token.json'

class KISTokenError(RuntimeError):
    pass


def _expiry(payload, now):
    # KIS can provide an absolute expiration timestamp or a duration.
    absolute = payload.get('access_token_token_expired')
    if isinstance(absolute, str) and absolute:
        try:
            dt = datetime.strptime(absolute, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
            # KIS timestamps may be local Korea time; use expires_in when available.
        except ValueError:
            pass
    duration = payload.get('expires_in', 3600)
    try:
        duration = int(duration)
    except (ValueError, TypeError):
        duration = 3600
    return now + max(60, min(duration, 86400))


def _write_private(path: Path, payload: dict):
    fd, tmp = tempfile.mkstemp(prefix='.kis-token-', dir=str(path.parent))
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as out:
            json.dump(payload, out, separators=(',', ':'))
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def get_token(key: str, secret: str, *, cache_path: str = DEFAULT_CACHE,
              post=requests.post, now_fn=time.time) -> str:
    if not key or not secret:
        raise KISTokenError('KIS credentials missing')
    path = Path(cache_path)
    if not path.parent.is_dir():
        raise KISTokenError('Private cache directory does not exist')
    identity = hashlib.sha256((key + ':' + secret).encode()).hexdigest()
    lock_path = path.with_suffix(path.suffix + '.lock')
    lock_fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o600)
    try:
        with os.fdopen(lock_fd, 'r+') as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            now = now_fn()
            try:
                with path.open('r', encoding='utf-8') as inp:
                    cache = json.load(inp)
            except (OSError, ValueError, TypeError):
                cache = {}
            if (cache.get('identity') == identity
                    and isinstance(cache.get('token'), str)
                    and cache.get('token')
                    and float(cache.get('expires_at', 0)) - now > 120):
                return cache['token']
            # Avoid immediate repeated requests following a failed attempt.
            if cache.get('identity') == identity and float(cache.get('retry_after', 0)) > now:
                raise KISTokenError('KIS token request cooling down; retry later')
            try:
                response = post(TOKEN_URL, json={
                    'grant_type': 'client_credentials', 'appkey': key,
                    'appsecret': secret}, timeout=10)
                response.raise_for_status()
                payload = response.json()
                token = payload.get('access_token')
                if not isinstance(token, str) or not token:
                    raise KISTokenError('KIS response did not contain an access token')
            except (requests.RequestException, ValueError, KISTokenError) as exc:
                _write_private(path, {'identity': identity, 'retry_after': now + 300})
                raise KISTokenError('KIS token request failed; 5-minute cooldown') from exc
            _write_private(path, {
                'identity': identity, 'token': token,
                'expires_at': _expiry(payload, now), 'retry_after': 0})
            return token
    except OSError as exc:
        raise KISTokenError('Token cache storage unavailable') from exc
