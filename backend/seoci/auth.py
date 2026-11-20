"""Local-file accounts and signed, seven-day browser sessions."""
import argparse
import base64
from contextlib import contextmanager
import fcntl
import getpass
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import tempfile
from threading import Lock
import time

from seoci.config import settings

COOKIE = "seoci_session"
SESSION_SECONDS = 7 * 24 * 60 * 60
ITERATIONS = 600_000
USERNAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z")


def hash_password(password):
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), ITERATIONS).hex()
    return f"pbkdf2_sha256${ITERATIONS}${salt}${digest}"


def verify_password(password, encoded):
    try:
        algorithm, iterations, salt, expected = encoded.split("$")
        count = int(iterations)
        if algorithm != "pbkdf2_sha256" or not 100_000 <= count <= 2_000_000:
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), count).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def users_path():
    return Path(settings.auth_users_file).expanduser()


def load_users():
    try:
        lines = users_path().read_text().splitlines()
    except FileNotFoundError:
        return {}
    users = {}
    for line in lines:
        if not line.strip():
            continue
        name, separator, encoded = line.partition(":")
        if not separator or not USERNAME.fullmatch(name) or not encoded:
            raise OSError("Invalid users file")
        users[name] = encoded
    return users


@contextmanager
def users_lock():
    path = users_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(str(path) + ".lock", os.O_CREAT | os.O_RDWR, 0o600)
    with os.fdopen(descriptor, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def write_private(path, content):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as output:
            temporary = output.name
            os.chmod(temporary, 0o600)
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def add_user(name, password, first_only=False):
    if not USERNAME.fullmatch(name) or not 8 <= len(password) <= 1024:
        raise ValueError("Use a valid username and a password of 8–1024 characters")
    if first_only and load_users():
        return False
    encoded = hash_password(password)
    with users_lock():
        users = load_users()
        if first_only and users:
            return False
        users[name] = encoded
        write_private(users_path(), "".join(f"{user}:{value}\n" for user, value in sorted(users.items())))
    return True


def signing_secret():
    if settings.auth_secret:
        return settings.auth_secret.encode()
    with users_lock():
        path = Path(str(users_path()) + ".secret")
        if not path.exists():
            write_private(path, secrets.token_urlsafe(48))
        secret = path.read_bytes().strip()
        if len(secret) < 32:
            raise OSError("Invalid session secret file")
        return secret


def signature(secret, value):
    return hmac.new(secret, value.encode(), hashlib.sha256).hexdigest()


def create_session(username, password_hash):
    secret = signing_secret()
    payload = {"u": username, "e": int(time.time()) + SESSION_SECONDS, "v": signature(secret, password_hash)}
    body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    return body + "." + signature(secret, body)


def session_user(token):
    if not token or len(token) > 2048:
        return None
    try:
        body, signed = token.split(".")
        secret = signing_secret()
        if not hmac.compare_digest(signature(secret, body), signed):
            return None
        payload = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
        if not isinstance(payload, dict) or not isinstance(payload.get("e"), int) or payload["e"] <= time.time():
            return None
        password_hash = load_users().get(payload.get("u"))
        if password_hash and hmac.compare_digest(signature(secret, password_hash), payload.get("v", "")):
            return payload["u"]
    except (ValueError, TypeError, KeyError, UnicodeError):
        pass
    return None


class LoginThrottle:
    def __init__(self):
        self.entries = {}
        self.lock = Lock()

    def blocked(self, key):
        with self.lock:
            self.entries = {k: value for k, value in self.entries.items() if value[1] > time.monotonic()}
            return self.entries.get(key, (0, 0))[0] >= 5

    def failed(self, key):
        with self.lock:
            count, deadline = self.entries.get(key, (0, time.monotonic() + 900))
            if len(self.entries) >= 10_000 and key not in self.entries:
                self.entries.pop(next(iter(self.entries)))
            self.entries[key] = (count + 1, deadline)

    def reset(self, key):
        with self.lock:
            self.entries.pop(key, None)


throttle = LoginThrottle()
DUMMY_HASH = hash_password(secrets.token_urlsafe(32))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Manage local SEO Content Intelligence accounts")
    commands = parser.add_subparsers(dest="command", required=True)
    add = commands.add_parser("add-user", help="Create or update a user")
    add.add_argument("name")
    args = parser.parse_args(argv)
    if not USERNAME.fullmatch(args.name):
        parser.error("Username must use 1–64 letters, digits, dots, underscores or hyphens")
    password = getpass.getpass("Password: ")
    if password != getpass.getpass("Confirm password: "):
        parser.error("Passwords do not match")
    try:
        add_user(args.name, password)
    except (ValueError, OSError):
        parser.error("Could not save user; check password length and file permissions")
    print(f"User {args.name} saved.")


if __name__ == "__main__":
    main()
