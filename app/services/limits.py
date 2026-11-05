# app/services/limits.py
"""
Rate limits on everything that checks a secret, per client IP.

Two budgets:

  login          officer and superadmin sign-ins, password changes and the
                 group finder (LOGIN_RATE_LIMIT)
  public-lookup  the group access code, member PINs and personal history
                 links (PUBLIC_LOOKUP_RATE_LIMIT)

Only failed attempts are counted: a view calls failed() when the secret
was wrong. Many members reach the site through one mobile network
address, so successful lookups must not use up each other's budget. Once
a budget is spent, every attempt from that address is refused (429) until
it recovers, right or wrong.

Behind a reverse proxy, set TRUSTED_PROXIES so the client's own address
is used rather than the proxy's.
"""
from flask import current_app, g

from app.extensions import limiter


def failed() -> None:
    """Count this request against its budget."""
    g.limited_attempt_failed = True


def _was_failure(_response) -> bool:
    # Called once per limit in the budget, so it must not clear the flag
    return g.get('limited_attempt_failed', False)


def _login_limit() -> str:
    return current_app.config['LOGIN_RATE_LIMIT']


def _lookup_limit() -> str:
    return current_app.config['PUBLIC_LOOKUP_RATE_LIMIT']


# Form posts only, so the pages still open while a budget is spent
login = limiter.shared_limit(_login_limit, scope='login', methods=['POST'], deduct_when=_was_failure)
public_lookup = limiter.shared_limit(_lookup_limit, scope='public-lookup', methods=['POST'],
                                     deduct_when=_was_failure)
# The personal link is opened with GET; same budget as the PIN
history_link = limiter.shared_limit(_lookup_limit, scope='public-lookup', deduct_when=_was_failure)
