"""Scope Git credentials to child environments; never put tokens in URLs/config."""
import base64
import os
from contextlib import contextmanager
from contextvars import ContextVar

_credential = ContextVar("git_credential", default=None)


@contextmanager
def git_auth(token):
    handle = _credential.set(token)
    try:
        yield
    finally:
        _credential.reset(handle)


def git_environment():
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    token = _credential.get()
    if token:
        basic = base64.b64encode(f"x-access-token:{token}".encode()).decode()
        env.update({"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "http.https://github.com/.extraheader", "GIT_CONFIG_VALUE_0": f"Authorization: Basic {basic}"})
    return env
