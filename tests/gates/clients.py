"""Interactive stock clients used to keep sessions open across another action."""

import os
import selectors
import shlex
import subprocess
import time

from native import checked, require


class Client:
    def __init__(self, target, args):
        self.args = args
        self.target = target
        self.buffer = b""

    def __enter__(self):
        self.target.safe_print(f"$ podman {shlex.join(self.args)}")
        self.process = subprocess.Popen(
            self.target.podman_args(*self.args), stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
        return self

    def send(self, sql):
        print(sql.strip(), flush=True)
        self.process.stdin.write((sql + "\n").encode())
        self.process.stdin.flush()

    def line(self, timeout=20):
        deadline = time.monotonic() + timeout
        with selectors.DefaultSelector() as selector:
            selector.register(self.process.stdout, selectors.EVENT_READ)
            while b"\n" not in self.buffer:
                if not selector.select(max(0, deadline - time.monotonic())):
                    raise AssertionError("client did not return a line within the deadline")
                data = os.read(self.process.stdout.fileno(), 65536)
                if not data:
                    raise AssertionError("client closed its output before returning the expected line")
                self.buffer += data
        line, self.buffer = self.buffer.split(b"\n", 1)
        value = line.decode(errors="replace")
        self.target.safe_print(value)
        return value

    def query(self, sql):
        self.send(sql)
        return self.line()

    def __exit__(self, *_):
        try:
            self.process.stdin.close()
        except BrokenPipeError:
            pass
        try:
            self.process.wait(5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
        self.process.stdout.close()


def until(predicate, seconds=20):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.05)
    raise AssertionError("the required server activity did not occur before the deadline")


def managed_client(target, args, label="default"):
    container = args[2]
    pidfile = f"/tmp/dl077-gate-client-{label}.pid"
    wrapper = (
        "sh", "-ec", 'echo "$$" > "$1"; shift; exec "$@"', "dl077-client",
        pidfile, *args[3:],
    )
    return Client(target, ("exec", "-i", container, *wrapper))


def kill_managed_client(target, container, label="default"):
    checked(target.podman(
        "exec", container, "sh", "-ec",
        'kill -KILL "$(cat "$1")"', "dl077-client", f"/tmp/dl077-gate-client-{label}.pid",
    ))
