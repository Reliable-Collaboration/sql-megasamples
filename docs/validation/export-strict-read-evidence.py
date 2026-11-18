"""Publish only completed, credential-free evidence for the strict-read PR."""
import datetime
import hashlib
import json
from pathlib import Path
import re

ROOT=Path.cwd()
BASE=ROOT/'build/strict-read'
assert ROOT==Path('/home/rcc-vstudio/working/sql-megasamples-upgrade')


def read(name):
    return json.loads((BASE/name).read_text())


def file_record(path):
    raw=path.read_bytes()
    return {'path':str(path.relative_to(ROOT)),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}


checkpoints=read('checkpoints.json')
expected=['pairs','dataset-flags','append-selectors','every-pair','mysql','postgres','sqlite','all']
assert set(checkpoints)==set(expected)
for name,row in checkpoints.items():
    assert row['reset']['status']==row['native']['status']=='Passed'
    assert set(row['reads'])=={'mysql','postgres','sqlite'}
    assert all(v['status']=='Passed' for v in row['reads'].values())
native_reads={'baseline':{e:read('baseline/reset-matrix-'+e+'.json') for e in ['mysql','postgres','sqlite']},'checkpoints':{}}
for name in expected:
    native_reads['checkpoints'][name]={}
    for engine in ['mysql','postgres','sqlite']:
        path=BASE/('checkpoint-'+name)/('reset-matrix-'+engine+'.json')
        observed=json.loads(path.read_text())
        assert observed['status']=='Passed'
        assert observed['databases']==native_reads['baseline'][engine]['databases']
        native_reads['checkpoints'][name][engine]={
            **{k:v for k,v in observed.items() if k!='databases'},
            'databases_reference':'native_read_fingerprints.baseline.'+engine+'.databases',
            'all_complete_table_fingerprints_equal_baseline':True,'receipt':file_record(path)}
steps=read('final-validation-steps.json')
assert steps and all(row['status']=='Passed' for row in steps.values())
restoration=read('restoration.json')
assert restoration['status']=='Passed'
isolation=read('isolation.json')
assert isolation['status']=='Passed'
matrices={}
for phase,directory in [('before','baseline'),('candidate','final-candidate'),('restored_main','restored-main')]:
    matrices[phase]={}
    for engine in ['mysql','postgres','sqlite']:
        row=read(directory+'/runtime-'+engine+'.json')
        assert row['results'] and all(v['status']=='Passed' for v in row['results'].values())
        matrices[phase][engine]=row
for engine in ['mysql','postgres','sqlite']:
    keys=set(matrices['before'][engine]['results'])
    assert set(matrices['candidate'][engine]['results'])==set(matrices['restored_main'][engine]['results'])==keys
before=read('baseline/privileges.json')
after=read('final-candidate/privileges.json')
grant_comparison={}
for db,old in before['postgres'].items():
    new=after['postgres'][db]
    indexed={(r['namespace'],r['signature']):r for r in new['routines']}
    for routine in old['routines']:
        updated=indexed[(routine['namespace'],routine['signature'])]
        assert routine['admin_execute']==updated['admin_execute']
        assert routine['superuser_execute']==updated['superuser_execute']
    def user_routines(row):
        return [r['signature'] for r in row['routines'] if r['demo_execute'] and r['namespace'] not in ('pg_catalog','information_schema')]
    assert not user_routines(new)
    assert not next(a for a in new['accounts'] if a['account']=='demo')['temporary']
    grant_comparison[db]={
        'before_accounts':old['accounts'],'candidate_accounts':new['accounts'],
        'before_demo_user_routines':user_routines(old),'candidate_demo_user_routines':user_routines(new),
        'before_demo_executable_count':sum(r['demo_execute'] for r in old['routines']),
        'candidate_demo_executable_count':sum(r['demo_execute'] for r in new['routines']),
        'existing_admin_and_superuser_routine_rights_unchanged':True,
        'large_object_creation':{label:[{key:r[key] for key in ['signature','demo_execute','admin_execute','superuser_execute']}
            for r in row['routines'] if r['name'] in ('lo_create','lo_creat','lo_import','lo_from_bytea')]
            for label,row in [('before',old),('candidate',new)]}}
assert before['mysql']['demo']['grants']==after['mysql']['demo']['grants']
assert before['mysql']['admin']['grants']==after['mysql']['admin']['grants']
assert before['mysql']['root']['grants']==after['mysql']['root']['grants']
images={}
for engine in ['mysql','postgres','sqlite']:
    text=(BASE/('test-image-'+engine+('-final' if engine=='postgres' else '')+'.log')).read_text()
    assert 'image test: 0 failure(s)' in text
    images[engine]={'status':'Passed','log':file_record(BASE/('test-image-'+engine+('-final' if engine=='postgres' else '')+'.log'))}
canaries=read('canary-results.json')
assert canaries['status']=='Passed'
log_canaries=[read('container-log-canaries-before-candidate.json'),read('container-log-canaries.json')]
assert all(row['status']=='Passed' for row in log_canaries)
writers={name:read('final-candidate/writer-'+name+'.json') for name in ['postgres-admin','postgres-postgres','mysql-admin','mysql-root']}
assert all(all(v['status']=='Passed' for v in row['results'].values()) for row in writers.values())
mysql_boundary=read('mysql-boundary.json')
assert mysql_boundary['write_denials']['status']=='Passed'
assert mysql_boundary['builtin_function_read_only_enforcement']['status']=='Unsupported'
red_log=BASE/'native-before-connected.log'
red_summary=re.search(r'^94 failed, 94 passed in .+$',red_log.read_text(),re.M)
assert red_summary,'missing connected failing baseline'
native_log=BASE/'native-final.log'
native_summary=re.search(r'^254 passed in .+$',native_log.read_text(),re.M)
assert native_summary,'missing passing native candidate gate'
receipt={
    'generated_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'main_before':'2cf1f3e9538ea2e90ef23f8715c5e08e4c7de848',
    'sources':json.loads((ROOT/'docs/validation/strict-read-sources.json').read_text()),
    'grants':{'before_read_at':before['read_at'],'candidate_read_at':after['read_at'],
              'postgres':grant_comparison,'mysql_before':before['mysql'],'mysql_candidate':after['mysql']},
    'executable_routines':json.loads((ROOT/'docs/validation/strict-read-executable-routines.json').read_text()),
    'test_first':{'connected_original_main':{'status':'Failed','expected_permission_regressions':True,'summary':red_summary.group(0),'log':file_record(red_log)},
                  'candidate_native_gate':{'status':'Passed','summary':native_summary.group(0),'log':file_record(native_log)}},
    'canonical_matrices':matrices,'native_read_fingerprints':native_reads,'checkpoints':checkpoints,'final_validation_steps':steps,
    'writer_scenarios':writers,'image_checks':images,'rotation':read('rotation-results.json'),
    'mysql_builtin_boundary':mysql_boundary,
    'restoration':restoration,'isolation':isolation,'canaries':canaries,'container_log_canaries':log_canaries,
    'credential_output_rule':{'status':'Failed','reason':'Published bootstrap credentials appeared in initial repository source inspection; no values are repeated here.'},
    'scope':{'live_cutover':'Not run','DataIntent_suites':'Not run','Docker_BuildKit_and_other_architectures':'Not run',
             'unconfigured_generated_benchmarks':'Not run','SQLite_server_accounts':'Unsupported',
             'MySQL_builtin_function_ACLs':'Unsupported; stored-routine ACLs do not control builtin functions'},
    'retained_logs':[file_record(p) for p in sorted(BASE.rglob('*.log')) if p.name not in ('canary-monitor.log',)]}
output=ROOT/'docs/validation/strict-read-2026-11-18.json'
output.write_text(json.dumps(receipt,indent=2)+'\n')
print('Passed: complete evidence exported; credential-output rule failure explicitly retained')
