"""Shared adapter substrate: env-overridable repo roots + missing-backend
state. Every adapter resolves its external repo through here so CI (or any
second machine) can point at pinned clones, and so a missing backend is a
declared NOT_CONFIGURED condition — never an Errno traceback leaking out
of a gate (fail closed, loudly labeled)."""
import os


class BackendMissing(Exception):
    pass


def repo_root(env_key, default):
    return os.environ.get(env_key, default)


def require_dir(path, name):
    if not os.path.isdir(path):
        raise BackendMissing("%s backend missing: %s" % (name, path))
    return path


def require_file(path, name):
    if not os.path.isfile(path):
        raise BackendMissing("%s backend missing: %s" % (name, path))
    return path
