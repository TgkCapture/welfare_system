"""
Production cookies only travel over HTTPS unless ALLOW_HTTP is set for a trial.
The setting is read when the app starts, so each case starts a fresh process.
"""
import json
import os
import subprocess
import sys

import pytest

_PROBE = ("import json; from app import create_app; c = create_app('production').config; "
          "print(json.dumps([c['SESSION_COOKIE_SECURE'], c['REMEMBER_COOKIE_SECURE']]))")


def _cookie_flags(tmp_path, **env):
    environ = {k: v for k, v in os.environ.items() if k != 'ALLOW_HTTP'}
    environ.update(SECRET_KEY='x' * 64, DATABASE_URL=f'sqlite:///{tmp_path / "p.db"}',
                   ENABLE_AUTO_CLEANUP='false', **env)
    out = subprocess.run([sys.executable, '-c', _PROBE], env=environ, capture_output=True, text=True,
                         cwd=os.path.dirname(os.path.dirname(__file__)), check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


@pytest.mark.parametrize('env, secure', [({}, True), ({'ALLOW_HTTP': '1'}, False), ({'ALLOW_HTTP': '0'}, True)])
def test_production_cookies_need_https_unless_allowed(tmp_path, env, secure):
    assert _cookie_flags(tmp_path, **env) == [secure, secure]
