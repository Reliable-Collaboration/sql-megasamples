# DL-077 version 1 feasibility gates

Each executable named `G-…` corresponds to one row in section 8.1 of
[the design](../../docs/design/templates-copies-and-accounts.md#81-version-1s-feasibility-gates).
The test uses native SQL, clients and filesystem operations. See the
[validation record](../../docs/validation/dl-077-v1-gates.md) for the run status.

Use a fresh disposable target for each gate. Several tests intentionally alter accounts,
kill clients, restart servers, fill a data mount or replace a container. Create the
targets with the memory settings of the corresponding service in `compose.yaml`.
The shared service and its store must stay outside the target. Capture the live inventory,
the isolated inventory, and the isolated stack's image and dataset fingerprints before
starting tests. Compare those inventories and fingerprints again after restoring the stack.

Point `DL077_GATE_TARGET` to a private JSON file. It supplies the following fields.

| Field | Value |
|---|---|
| `env_script` | Absolute path to the isolated store's `env.sh` |
| `graph_root` | The isolated store's expected absolute GraphRoot |
| `owner` | A unique value starting with `dl077-` and at least eight more characters |
| `containers` | A map from each required fixture name to the task-owned container name. Each bears `org.sql-megasamples.gates.owner=<owner>`. |
| `sqlite_bind` | For G-19a and G-20, the private scratch directory also mounted at `/scratch` in `sqlite_peer`. The peer needs `sh`, `ln` and util-linux `flock`. |
| `sqlite_full_mount` | For G-19c, an empty, dedicated, disposable filesystem of up to 128 MiB with `posix_fallocate` support. |
| `mysql_image_datasets` | For G-18a and G-18b, the dataset IDs built into the image. |
| `canary_dir` | For G-16, an ignored, private `.local` directory with private `mysql-demo` and `mysql-demo-alternate` canary files. |

The shell runner sources the designated environment for each Podman invocation. It
checks GraphRoot before opening a target and checks each container's ownership label
before it can run SQL, stop or restart that container. It checks `MemAvailable` before
starting or restarting one. Set `DL077_GATE_CAPACITY_WAIT` to a number of seconds
to wait for the threshold before a start. A guard failure exits 77. G-19b only needs a private
temporary directory. G-19c can run inside the container that owns its bounded
filesystem and uses only the manifest's filesystem path there.

| Fixtures | Provisioning |
|---|---|
| `postgres`, `mysql`, `sqlite` | Images from main at `e61335f`. Use isolated copies with the baseline datasets when a gate reads the image catalog or fingerprint. PostgreSQL's local socket must use the shipped local maintenance path. |
| `postgres_pr14` | PostgreSQL image built from PR #14 at `2879fc4`. |
| `postgres_hook`, `postgres_hook_unloaded` | Two fresh volumes with the same PostgreSQL 18 test image. Build the test library under `prototype/` with matching server headers and PGXS. Preload `dl077_gate_hook` in the first target only. |
| `mysql_no_binlog` | Same MySQL image as `mysql`, with `--skip-log-bin` and the same existing server limits. |
| `mysql`, `mysql_replacement` for G-33a | Build a fixture from a scratch copy of `engines/mysql/Dockerfile`. Remove `/var/lib/mysql/auto.cnf` in the builder immediately after its final MySQL shutdown. Seed each container from that fixture into a distinct fresh volume. |
| `postgres_small`, `mysql_small` | Small fixtures on separate data filesystems up to 2 GiB. The test fills and frees space on the data filesystem inside the container. |
| `postgres_replacement`, `mysql_replacement`, `sqlite_replacement` | Created and stopped, using the corresponding fixture's image and a distinct fresh data volume. For G-33b use the same loopback publications as the old targets. |
| `postgres_reference`, `mysql_reference` | Independent fixtures supplying source data or the untouched image fingerprint. |
| `postgres_peer`, `mysql_peer` | Client containers on the isolated stack network, with the relevant server container reachable by its name. |
| `postgres_published_peer`, `mysql_published_peer` | Client containers that reach the task-owned server's published loopback port. |
| `adminer`, `phpmyadmin`, `dbgate`, `cloudbeaver` | Bundled consoles pointed at the task's engines with synthetic settings. Use fresh consoles with no prior sessions for G-32b. |
| `browser` | For G-32a, an owned browser container on the console network with Python Playwright and Chromium. Bind this test directory at `/gates`. |

Supply the PostgreSQL peer clients with a private libpq passfile. The MySQL clients
read private synthetic option files under `/run/dl077/` named `mysql-root.cnf`,
`mysql-admin.cnf` and `mysql-demo.cnf`. Use distinct local and network credentials
where the image has distinct accounts. Client calls pass the option file path and
stream SQL on stdin. Keep the canary values and published endpoints in the ignored
deployment configuration. During G-16 the tester checks that MySQL's raw query
logging is disabled before submitting a password statement, and records only the
statement name, exit code, server error code and sign-in result.

Run an individual file from the repository root.

```sh
tests/gates/G-7b
tests/gates/G-19b
```
