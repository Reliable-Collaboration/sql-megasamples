-- Accounts for the megasamples image (knowledge/decisions/database-naming-convention.md).
-- Runs in the BUILDER stage: the official entrypoint's docker_setup_db never executes on a
-- pre-populated data directory, so root@'%', the demo user and the admin user are all created here.
-- entrypoint-wrapper.sh applies MYSQL_ROOT_PASSWORD / DEMO_PASSWORD / ADMIN_PASSWORD at run time.

-- `mysqld --initialize-insecure` leaves root@localhost with an EMPTY password; the entrypoint's
-- docker_setup_db would normally set it, but that never runs on a baked data directory, so the
-- image would otherwise ship with passwordless local root. Verified at P-03 on 2026-09-02.
ALTER USER 'root'@'localhost' IDENTIFIED BY 'root';

CREATE USER IF NOT EXISTS 'root'@'%'  IDENTIFIED BY 'root';
GRANT ALL PRIVILEGES ON *.* TO 'root'@'%' WITH GRANT OPTION;

CREATE USER IF NOT EXISTS 'admin'@'%' IDENTIFIED BY 'admin';
GRANT ALL PRIVILEGES ON *.* TO 'admin'@'%' WITH GRANT OPTION;

-- read-only demo account: its grants are made per schema at build time (megasamples/mysql_templates.py,
-- demo_read_grants); no write privilege anywhere.
CREATE USER IF NOT EXISTS 'demo'@'%'  IDENTIFIED BY 'demo';

-- provenance registry; megasamples/registry.py regenerates 10-registry.sql with the real rows.
CREATE DATABASE IF NOT EXISTS megasamples;
CREATE TABLE IF NOT EXISTS megasamples.datasets (
  name          VARCHAR(64)  NOT NULL PRIMARY KEY,
  tier          VARCHAR(24)  NOT NULL,
  record        VARCHAR(128) NOT NULL,
  upstream_version VARCHAR(128),
  licenses      JSON,
  artifacts     JSON,
  row_counts    JSON,
  build_id      VARCHAR(64)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

FLUSH PRIVILEGES;
