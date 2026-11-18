"""Exercise changed SQL-file/LOCAL INFILE and dump/restore clients on a pristine copy."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

from megasamples import config, reset
from megasamples.credentials import client, session
from megasamples.engines import get
from megasamples.engines.mysql import server as mysql

ROOT = Path.cwd()
OUT = ROOT / 'build/credential-upgrade'
assert ROOT == Path('/home/rcc-vstudio/working/sql-megasamples-upgrade')
assert os.environ['CONTAINERS_STORAGE_CONF'] == str(ROOT.parent / 'sql-megasamples-upgrade-env/storage.conf')
assert os.environ['DOCKER_HOST'] == 'unix://' + str(ROOT.parent / 'sql-megasamples-upgrade-env/podman.sock')
assert os.environ['COMPOSE_PROJECT_NAME'] == 'megasamples-upgrade'
assert subprocess.check_output(['docker', 'info', '--format', '{{.DockerRootDir}}'], text=True).strip().startswith(str(ROOT.parent / 'sql-megasamples-upgrade-env/'))
password = config.passwords()['MYSQL_ROOT_PASSWORD']
started = time.monotonic()
with session(), reset.Pristine(get('mysql'), lambda c: reset.my(c, 'SELECT 1').returncode == 0) as pristine:
    mysql.NAME, mysql.PW = pristine.name, password
    csv = OUT / 'private-client-probe.tsv'
    csv.write_bytes(b'1\talpha\t000102feff\n')
    subprocess.run(['docker', 'cp', str(csv), pristine.name + ':/tmp/private-client-probe.tsv'], capture_output=True, check=True)
    path = OUT / 'private-client-probe.sql'
    path.write_text("""CREATE DATABASE credential_helper_probe;
CREATE TABLE credential_helper_probe.t(id INT PRIMARY KEY, txt VARCHAR(100), b VARBINARY(20));
LOAD DATA LOCAL INFILE '/tmp/private-client-probe.tsv' INTO TABLE credential_helper_probe.t
FIELDS TERMINATED BY '\\t' (id,txt,@b) SET b=UNHEX(@b);
INSERT INTO credential_helper_probe.t VALUES (2,CONVERT(0xCEB10A74616209 USING utf8mb4),0x000102FEFF);
""")
    mysql.sql('SET GLOBAL local_infile=ON')  # fixture-only, as on the build server
    mysql.sql_file(str(path))
    sql = 'SELECT id,HEX(txt),HEX(b) FROM credential_helper_probe.t ORDER BY id'
    expected = [['1', '616C706861', '000102FEFF'], ['2', 'CEB10A74616209', '000102FEFF']]
    assert mysql.rows(sql) == expected
    with client('mysql', pristine.name, 'root', password, 'mysqldump') as command:
        dumped = subprocess.run([*command, '--databases', 'credential_helper_probe', '--hex-blob', '--set-gtid-purged=OFF'], capture_output=True, text=True)
    assert dumped.returncode == 0, 'private-file dump failed'
    assert password not in dumped.stdout and password not in dumped.stderr
    mysql.sql('DROP DATABASE credential_helper_probe')
    with client('mysql', pristine.name, 'root', password) as command:
        restored = subprocess.run(command, input=dumped.stdout, capture_output=True, text=True)
    assert restored.returncode == 0 and mysql.rows(sql) == expected, 'private-file restore changed data'
    row = dict(status='Passed', sql_file='Passed', local_infile='Passed', binary_unicode_newline_tab_roundtrip='Passed',
               dump_restore='Passed', observed_rows=expected, dump_sha256=hashlib.sha256(dumped.stdout.encode()).hexdigest(),
               password_in_output=False, seconds=time.monotonic() - started, pristine_container_removed_on_exit=True)
assert subprocess.run(['docker', 'inspect', pristine.name], capture_output=True).returncode != 0, 'pristine helper probe was not removed'
(OUT / 'private-client-probe.json').write_text(json.dumps(row, indent=2) + '\n')
print('Passed: private-file SQL load, LOCAL INFILE, binary/Unicode/newline/tab data and native dump/restore', flush=True)
