/* Close PostgreSQL's database-ACL default at creation, before commit.
 * Database ACLs are not copied from templates and CREATE DATABASE cannot be
 * handled by an event trigger. Run ordinary GRANT/REVOKE through SPI as the
 * database creator (no privilege elevation). The trusted writer retains TEMP.
 */
#include "postgres.h"
#include "fmgr.h"
#include "executor/spi.h"
#include "tcop/utility.h"
#include "utils/builtins.h"

PG_MODULE_MAGIC;
void _PG_init(void);
static ProcessUtility_hook_type previous_hook;

static void
read_policy_utility(PlannedStmt *pstmt, const char *queryString,
                    bool readOnlyTree, ProcessUtilityContext context,
                    ParamListInfo params, QueryEnvironment *queryEnv,
                    DestReceiver *dest, QueryCompletion *qc)
{
    Node *stmt = pstmt->utilityStmt;

    if (previous_hook)
        previous_hook(pstmt, queryString, readOnlyTree, context, params, queryEnv, dest, qc);
    else
        standard_ProcessUtility(pstmt, queryString, readOnlyTree, context, params, queryEnv, dest, qc);

    if (IsA(stmt, CreatedbStmt))
    {
        const char *name = quote_identifier(((CreatedbStmt *) stmt)->dbname);
        char *sql = psprintf("REVOKE TEMPORARY ON DATABASE %s FROM PUBLIC; "
                            "GRANT TEMPORARY ON DATABASE %s TO admin", name, name);
        if (SPI_connect() != SPI_OK_CONNECT)
            elog(ERROR, "read policy could not connect to SPI");
        if (SPI_execute(sql, false, 0) < 0)
            elog(ERROR, "read policy could not secure the new database");
        SPI_finish();
        pfree(sql);
    }
}

void
_PG_init(void)
{
    previous_hook = ProcessUtility_hook;
    ProcessUtility_hook = read_policy_utility;
}
