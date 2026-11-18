"""Native clients with private option/pass files, streamed over stdin, never password argv.

The daemon and container owner can inspect their own resources. Temporary files are
0600 within a 0700 directory and removed on success and failure. Client-specific
environment overrides contain only a PGPASSFILE path. Container startup environment
metadata remains visible to its owner through the private daemon socket.
"""
from contextlib import contextmanager, ExitStack
from contextvars import ContextVar
import json, subprocess, tempfile


def mysql_options(user, password):
    def quote(value):
        for char, escaped in [('\\', '\\\\'), ('"', '\\"'), ('\n', '\\n'), ('\r', '\\r'), ('\t', '\\t')]:
            value = value.replace(char, escaped)
        return '"' + value + '"'
    return '[client]\nuser=' + quote(user) + '\npassword=' + quote(password) + '\n'


def pgpass(user, password):
    if '\n' in password or '\r' in password:
        raise ValueError('PostgreSQL pass files require a single-line password')
    escape = lambda value: value.replace('\\', '\\\\').replace(':', '\\:')
    return '*:*:*:' + escape(user) + ':' + escape(password) + '\n'


@contextmanager
def _private_client(engine, container, user, password, program=None, host=None, port=None):
    """Yield a docker exec argv prefix for mysql/psql (or their dump/restore tools)."""
    run = lambda args, **kw: subprocess.run(args, capture_output=True, text=True, **kw)
    made = run(['docker', 'exec', container, 'mktemp', '-d', '/tmp/megasamples-auth.XXXXXX'])
    directory = made.stdout.strip()
    if made.returncode or not directory.startswith('/tmp/megasamples-auth.') or '\n' in directory:
        raise RuntimeError('could not create a private client directory')
    try:
        if host is None:
            if engine == 'postgres':
                # The baked cluster trusts loopback. Use its own network address
                # so maintenance actually authenticates through the shipped SCRAM rule.
                inspected = run(['docker', 'inspect', '-f', '{{json .NetworkSettings.Networks}}', container])
                if inspected.returncode:
                    raise RuntimeError('could not inspect the PostgreSQL client address')
                networks = json.loads(inspected.stdout)
                host = next((n['IPAddress'] for n in networks.values() if n.get('IPAddress')), None)
                if not host:
                    raise RuntimeError('PostgreSQL maintenance requires a container network address')
            else:
                host = '127.0.0.1'
        if engine == 'mysql':
            path, contents = directory + '/client.cnf', mysql_options(user, password)
            command = ['docker', 'exec', '-i', container, program or 'mysql', '--defaults-extra-file=' + path,
                       '--host=' + host, '--protocol=TCP']
            if port:
                command += ['--port=' + str(port)]
        elif engine == 'postgres':
            path, contents = directory + '/pgpass', pgpass(user, password)
            command = ['docker', 'exec', '-i', '-e', 'PGPASSFILE=' + path, container, program or 'psql',
                       '-w', '-h', host, '-U', user]
            if port:
                command += ['-p', str(port)]
        else:
            raise ValueError('private clients support mysql and postgres')
        written = run(['docker', 'exec', '-i', container, 'sh', '-c',
                       'umask 077; cat > "$1"', 'sh', path], input=contents)
        if written.returncode:
            raise RuntimeError('could not write private client credentials')
        yield command
    finally:
        run(['docker', 'exec', container, 'rm', '-rf', directory])


@contextmanager
def environment_file(values):
    """A Docker --env-file for startup overrides; no values in process arguments."""
    with tempfile.NamedTemporaryFile(mode="w", prefix="megasamples-", suffix=".env") as stream:
        for key, value in values.items():
            if any(c in value for c in "\n\r\0"):
                raise ValueError("startup overrides require single-line passwords")
            stream.write(key + "=" + value + "\n")
        stream.flush()
        yield stream.name


_SESSION = ContextVar("megasamples_private_clients", default=None)


@contextmanager
def session():
    """Reuse a private file within one command; clean every file when that command ends.

    A full corpus issues thousands of queries. Recreating a private file for every
    query needlessly multiplies container execs. Context-local sessions also keep
    concurrent commands independent. Password/host/program changes use separate files.
    """
    if _SESSION.get() is not None:
        yield
        return
    with ExitStack() as files:
        token = _SESSION.set(({}, files))
        try:
            yield
        finally:
            _SESSION.reset(token)


@contextmanager
def client(engine, container, user, password, program=None, host=None, port=None):
    active = _SESSION.get()
    if active is None:
        with _private_client(engine, container, user, password, program, host, port) as command:
            yield command
    else:
        cache, files = active
        key = (engine, container, user, password, program, host, port)
        if key not in cache:
            cache[key] = files.enter_context(_private_client(*key))
        yield list(cache[key])
