"""Copy commands and the version 1 machine-readable response."""

import argparse
from datetime import datetime, timedelta, timezone
import json
import math
import os
import re
import stat
import sys

PREFIX = re.compile(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)*", re.ASCII)
LABEL = re.compile(r"[a-z0-9]{1,24}", re.ASCII)
IDENTITY = re.compile(r"[0-9a-f]{32}", re.ASCII)
NAME = re.compile(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)*_[0-9a-f]{12}", re.ASCII)
ENGINES = ("postgres", "mysql", "sqlite")


class CopyError(Exception):
    def __init__(self, status, code, message, identity=None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.identity = identity


class Help(Exception):
    pass


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise CopyError(2, "usage", message)

    def print_help(self, file=None):
        raise Help(self.format_help())


def prefix_is_valid(value):
    return isinstance(value, str) and len(value) <= 16 and bool(PREFIX.fullmatch(value)) and value != "working"


def database_is_valid(value):
    return (isinstance(value, str) and len(value) <= 33 and bool(PREFIX.fullmatch(value))
            and not value.endswith("_start") and value != "megasamples")


def copy_name_is_valid(value):
    return isinstance(value, str) and len(value) <= 63 and bool(NAME.fullmatch(value))


def now():
    return datetime.now(timezone.utc)


def expiry(seconds):
    return (now() + timedelta(seconds=seconds)).isoformat()


def duration(value):
    match = re.fullmatch(r"([0-9]{1,6})([smhd])", value)
    if match:
        amount, unit = match.groups()
        seconds = int(amount) * {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit]
        if 60 <= seconds <= 604800:
            return seconds
    raise argparse.ArgumentTypeError("lease must be between 1m and 7d")


def nonnegative_seconds(value):
    try:
        seconds = float(value)
    except ValueError:
        seconds = math.nan
    if not math.isfinite(seconds) or seconds < 0:
        raise argparse.ArgumentTypeError("expected a nonnegative number of seconds")
    return seconds


def parse(argv):
    parser = Parser(prog="megasamples copy")
    commands = parser.add_subparsers(dest="action", required=True)
    for action in ("create", "show", "list", "drop", "renew", "release", "sweep"):
        command = commands.add_parser(action)
        command.add_argument("target")
        command.add_argument("--templates")
        command.add_argument("--dir")
        command.add_argument("--host")
        command.add_argument("--port", type=int)
        command.add_argument("--user")
        command.add_argument("--connect-timeout", type=nonnegative_seconds)
        passwords = command.add_mutually_exclusive_group()
        passwords.add_argument("--password-file")
        passwords.add_argument("--password-stdin", action="store_true")
        if action in ("create", "list", "sweep"):
            command.add_argument("--prefix", required=True)
        if action in ("create", "list"):
            command.add_argument("--label", required=action == "create")
        if action in ("drop", "renew", "release"):
            command.add_argument("--identity", required=True)
        if action in ("create", "renew"):
            command.add_argument("--lease", required=action == "renew", type=duration, default="24h")
        if action == "drop":
            command.add_argument("--wait", type=nonnegative_seconds, default=0)
        if action == "sweep":
            command.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    args.engine, separator, args.name = args.target.partition(":")
    if args.engine not in ENGINES or bool(separator) == (args.action in ("list", "sweep")):
        parser.error("expected ENGINE for list or sweep, and ENGINE:NAME otherwise")
    if getattr(args, "prefix", None) is not None and not prefix_is_valid(args.prefix):
        parser.error("invalid namespace prefix")
    if getattr(args, "label", None) is not None and not LABEL.fullmatch(args.label):
        parser.error("invalid label")
    if getattr(args, "identity", None) is not None and not IDENTITY.fullmatch(args.identity):
        parser.error("invalid copy identity")
    if args.action == "create":
        if not database_is_valid(args.name) or len(args.prefix) + len(args.name) + 14 > 63:
            parser.error("invalid database or copy name length")
    elif separator and not copy_name_is_valid(args.name):
        parser.error("invalid copy name")
    server_options = (args.host, args.port, args.user, args.connect_timeout,
                      args.password_file, args.password_stdin or None)
    if args.engine == "sqlite":
        if not args.templates or not args.dir or any(option is not None for option in server_options):
            parser.error("sqlite requires --templates and --dir")
    else:
        if args.templates is not None or args.dir is not None:
            parser.error("--templates and --dir are for sqlite")
        if (not args.host or not args.user or not (args.password_file or args.password_stdin)
                or args.port is not None and not 1 <= args.port <= 65535
                or args.connect_timeout is not None and args.connect_timeout <= 0):
            parser.error("a server requires a host, user and private password source")
    return args


def read_password(args):
    try:
        if args.password_stdin:
            data = sys.stdin.buffer.read(65537)
        else:
            flags = os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW
            with os.fdopen(os.open(args.password_file, flags), "rb") as stream:
                status = os.fstat(stream.fileno())
                if (status.st_uid != os.geteuid() or status.st_mode & 0o077
                        or not stat.S_ISREG(status.st_mode)):
                    raise ValueError("private password file required")
                data = stream.read(65537)
        if len(data) > 65536:
            raise ValueError("password source is too large")
        password = data.decode("utf-8").removesuffix("\n").removesuffix("\r")
        if not password or "\x00" in password:
            raise ValueError("password is missing")
        return password
    except (OSError, ValueError):
        raise CopyError(2, "password-source", "a private password source is required") from None


def main(argv):
    reply = {
        "schema": 1, "interface": 1, "command": "copy",
        "ok": False, "exit": 0, "volume": None, "result": None,
        "error": None, "warnings": [],
    }
    if argv and argv[0] in ("create", "show", "list", "drop", "renew", "release", "sweep"):
        reply["command"] = "copy " + argv[0]
    try:
        args = parse(argv)
        if args.engine == "sqlite":
            from megasamples.copy_sqlite import SQLiteCopies

            copies = SQLiteCopies(args)
            reply["result"] = getattr(copies, args.action)()
            reply["warnings"] = copies.warnings
        elif args.engine == "postgres":
            from megasamples.copy_postgres import open_postgres

            with open_postgres(args, read_password(args)) as copies:
                reply["volume"] = copies.volume
                reply["result"] = getattr(copies, args.action)()
                reply["warnings"] = copies.warnings
        else:
            raise CopyError(4, "no-template", "this build offers SQLite copy commands")
    except Help as help_message:
        reply["result"] = {"usage": str(help_message)}
    except CopyError as error:
        reply["exit"] = error.status
        reply["error"] = {"code": error.code, "message": str(error), "identity": error.identity}
    except Exception:
        reply["exit"] = 1
        reply["error"] = {"code": "internal", "message": "copy command failed unexpectedly", "identity": None}
    reply["ok"] = reply["exit"] == 0
    print(json.dumps(reply, ensure_ascii=True))
    return reply["exit"]
