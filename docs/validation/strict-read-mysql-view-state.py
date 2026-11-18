"""Native strict-rule probe for session writes through MySQL employee views.

The evidence records the known failure separately from direct EXECUTE grants.
No sample values or session-variable values are printed or stored.
"""
import datetime,json
from pathlib import Path
from docs.validation.strict_read_clients import query
sql="SELECT @max_date IS NULL; SELECT manager IS NULL FROM v_full_departments LIMIT 1; SELECT department IS NULL FROM v_full_employees LIMIT 1; SELECT @max_date IS NULL"
r=query('mysql','megasamples-mysql','demo','employees',sql)
assert r.returncode==0,'employee read-view probe failed'
rows=r.stdout.strip().splitlines()
assert len(rows)==4 and rows[1] in ('0','1') and rows[2] in ('0','1')
before,after=rows[0]=='1',rows[-1]=='1'
metadata=query('mysql','megasamples-mysql','demo','employees',"SELECT table_name,security_type FROM information_schema.views WHERE table_schema=DATABASE() AND table_name IN ('v_full_departments','v_full_employees') ORDER BY table_name",separator='\t')
assert metadata.returncode==0
security=dict(line.split('\t') for line in metadata.stdout.strip().splitlines())
assert len(security)==2 and set(security.values())=={'DEFINER'}
receipt={'view_security_types':security,'read_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'account':'demo','expected':'Reading both views leaves the initially unset @max_date session variable unset','initially_unset':before,'finally_unset':after,'strict_read_view_session_state':{'status':'Passed' if before and after else 'Failed'},'view_expressions_evaluated':'Passed','no_data_values_recorded':True,'initial_diagnostic':'Failed: an MD5 projection was refused; the final probe evaluates the same view columns using NULL predicates'}
Path('build/strict-read/mysql-view-state.json').write_text(json.dumps(receipt,indent=2)+'\n')
print('Native MySQL view-session-state criterion: '+receipt['strict_read_view_session_state']['status'],flush=True)

raise SystemExit(1 if receipt['strict_read_view_session_state']['status']=='Failed' else 0)
