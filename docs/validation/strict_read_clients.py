"""Native protocol clients for repeated isolated permission tests.

Each call opens a fresh authenticated connection, matching the CLI tests. No
password enters subprocess arguments, connection strings, or public environments.
Image gates retain the real psql/mysql CLI paths as an independent check.
"""
from contextlib import closing
from functools import lru_cache
import json
import os
import subprocess

from megasamples import config


@lru_cache(maxsize=None)
def endpoint(container,engine):
    assert os.environ['COMPOSE_PROJECT_NAME']=='megasamples-upgrade'
    assert os.environ['CONTAINERS_STORAGE_CONF']=='/home/rcc-vstudio/working/sql-megasamples-upgrade-env/storage.conf'
    assert os.environ['DOCKER_HOST']=='unix:///home/rcc-vstudio/working/sql-megasamples-upgrade-env/podman.sock'
    p=subprocess.run(['docker','inspect','-f','{{json .NetworkSettings.Ports}}',container],text=True,capture_output=True)
    if p.returncode:
        raise RuntimeError('could not inspect isolated native endpoint')
    internal='5432/tcp' if engine=='postgres' else '3306/tcp'
    bindings=json.loads(p.stdout).get(internal) or []
    if not bindings or bindings[0]['HostIp']!='127.0.0.1':
        raise RuntimeError('native protocol test requires a published localhost port')
    port=int(bindings[0]['HostPort'])
    assert port not in (3306,5432), 'refusing live-forwarder ports'
    return '127.0.0.1',port


def query(engine,container,user,database,sql,separator=None):
    secret=config.passwords()
    key={'postgres':'POSTGRES_PASSWORD','root':'MYSQL_ROOT_PASSWORD'}.get(user,user.upper()+'_PASSWORD')
    args=['native-protocol',engine,user,database]
    lines=[]
    try:
        host,port=endpoint(container,engine)
        if engine=='postgres':
            import psycopg
            connection=psycopg.connect(host=host,port=port,user=user,password=secret[key],
                                      dbname=database,autocommit=True,connect_timeout=10)
        else:
            import pymysql
            from pymysql.constants import CLIENT
            connection=pymysql.connect(host=host,port=port,user=user,password=secret[key],
                database=database,autocommit=True,charset='utf8mb4',client_flag=CLIENT.MULTI_STATEMENTS,
                connect_timeout=10)
        with closing(connection),connection.cursor() as cursor:
            cursor.execute(sql)
            while True:
                if cursor.description:
                    for row in cursor.fetchall():
                        def value(item):
                            if item is None:
                                return '' if engine=='postgres' else 'NULL'
                            if isinstance(item,bool) and engine=='postgres':
                                return 't' if item else 'f'
                            return str(item)
                        delimiter=separator if separator is not None else ('|' if engine=='postgres' else '\t')
                        lines.append(delimiter.join(value(item) for item in row))
                if not cursor.nextset():
                    break
        return subprocess.CompletedProcess(args,0,'\n'.join(lines)+'\n' if lines else '','')
    except Exception as exc:
        # Driver error messages are useful, connection-argument reprs are not.
        error=str(exc)
        for password in secret.values():
            error=error.replace(password,'[credential omitted]')
        return subprocess.CompletedProcess(args,1,'',error)
