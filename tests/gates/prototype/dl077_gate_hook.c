/*
 * DL-077 gate prototype. Load only into a disposable PostgreSQL 18 instance.
 * Implements the cases for rules 2 and 4 and the deliberate G-4b error.
 */
#include "postgres.h"

#include "access/htup_details.h"
#include "catalog/pg_authid.h"
#include "catalog/pg_type_d.h"
#include "commands/defrem.h"
#include "executor/spi.h"
#include "fmgr.h"
#include "miscadmin.h"
#include "nodes/parsenodes.h"
#include "tcop/utility.h"
#include "utils/builtins.h"
#include "utils/syscache.h"

PG_MODULE_MAGIC;
void _PG_init(void);

static ProcessUtility_hook_type next_utility;

static bool
may_alter_roles(Oid user)
{
    HeapTuple tuple = SearchSysCache1(AUTHOID, ObjectIdGetDatum(user));
    bool permitted;

    if (!HeapTupleIsValid(tuple))
        elog(ERROR, "cannot look up current role");
    permitted = ((Form_pg_authid) GETSTRUCT(tuple))->rolcreaterole;
    ReleaseSysCache(tuple);
    return permitted;
}

static void
namespace_check(Node *stmt)
{
    static const char *const namespaces =
        "SELECT substr(rolname::text, 18, length(rolname::text) - 23) "
        "FROM pg_roles WHERE starts_with(rolname::text, 'megasamples_copy_') "
        "AND right(rolname::text, 6) = '_owner' "
        "AND pg_has_role($1, oid, 'MEMBER')";
    static const char *const template_check =
        "SELECT 1 FROM pg_database d JOIN pg_roles r ON r.oid=d.datdba "
        "WHERE d.datname::text = $1 AND d.datistemplate AND NOT d.datallowconn "
        "AND r.rolsuper AND starts_with("
        "shobj_description(d.oid, 'pg_database'), 'megasamples-template/1 {')";
    Oid role_type = OIDOID;
    Datum role = ObjectIdGetDatum(GetUserId());
    uint64 count;
    char **prefixes;
    CreatedbStmt *create;
    const char *source = "template1";
    size_t source_length;
    ListCell *option;
    Oid source_type = TEXTOID;
    Datum source_arg;
    bool valid_destination = false;

    if (SPI_connect() != SPI_OK_CONNECT)
        elog(ERROR, "gate prototype could not connect to SPI");
    if (SPI_execute_with_args(namespaces, 1, &role_type, &role, NULL, true, 0) != SPI_OK_SELECT)
        elog(ERROR, "gate prototype could not read namespace markers");
    count = SPI_processed;
    if (count == 0)
    {
        SPI_finish();
        return;
    }
    if (IsA(stmt, RenameStmt))
        ereport(ERROR, (errcode(ERRCODE_INSUFFICIENT_PRIVILEGE),
                        errmsg("gate prototype: rename refused")));

    prefixes = palloc_array(char *, count);
    for (uint64 i = 0; i < count; i++)
        prefixes[i] = SPI_getvalue(SPI_tuptable->vals[i], SPI_tuptable->tupdesc, 1);

    create = castNode(CreatedbStmt, stmt);
    foreach(option, create->options)
    {
        DefElem *def = lfirst_node(DefElem, option);
        if (strcmp(def->defname, "template") == 0)
            source = defGetString(def);
    }
    source_length = strlen(source);
    source_arg = CStringGetTextDatum(source);
    if (SPI_execute_with_args(template_check, 1, &source_type,
                              &source_arg, NULL, true, 1) != SPI_OK_SELECT)
        elog(ERROR, "gate prototype could not read template registration");
    if (source_length <= 6 || strcmp(source + source_length - 6, "_start") != 0 ||
        SPI_processed != 1)
        ereport(ERROR, (errcode(ERRCODE_INSUFFICIENT_PRIVILEGE),
                        errmsg("gate prototype: source refused")));

    for (uint64 i = 0; i < count; i++)
    {
        const char *stem = psprintf("%s_%.*s_", prefixes[i],
                                    (int) source_length - 6, source);
        size_t length = strlen(stem);

        if (strncmp(create->dbname, stem, length) == 0 &&
            strlen(create->dbname + length) == 12 &&
            strspn(create->dbname + length, "0123456789abcdef") == 12)
            valid_destination = true;
    }
    SPI_finish();
    if (!valid_destination)
        ereport(ERROR, (errcode(ERRCODE_INSUFFICIENT_PRIVILEGE),
                        errmsg("gate prototype: destination refused")));
}

static void
gate_utility(PlannedStmt *pstmt, const char *query, bool read_only,
             ProcessUtilityContext context, ParamListInfo params,
             QueryEnvironment *env, DestReceiver *dest, QueryCompletion *qc)
{
    Node *stmt = pstmt->utilityStmt;

    if (!superuser())
    {
        if ((IsA(stmt, AlterRoleStmt) || IsA(stmt, AlterRoleSetStmt) ||
             IsA(stmt, AlterDefaultPrivilegesStmt)) && !may_alter_roles(GetUserId()))
            ereport(ERROR, (errcode(ERRCODE_INSUFFICIENT_PRIVILEGE),
                            errmsg("gate prototype: role change refused")));

        if (IsA(stmt, CreatedbStmt) ||
            (IsA(stmt, RenameStmt) && ((RenameStmt *) stmt)->renameType == OBJECT_DATABASE))
            namespace_check(stmt);
    }

    if (next_utility)
        next_utility(pstmt, query, read_only, context, params, env, dest, qc);
    else
        standard_ProcessUtility(pstmt, query, read_only, context, params, env, dest, qc);

    if (IsA(stmt, CreatedbStmt) &&
        strcmp(((CreatedbStmt *) stmt)->dbname, "gate_after_copy_error") == 0)
        ereport(ERROR, (errcode(ERRCODE_RAISE_EXCEPTION),
                        errmsg("gate prototype: injected after CREATE DATABASE")));
}

void
_PG_init(void)
{
    next_utility = ProcessUtility_hook;
    ProcessUtility_hook = gate_utility;
}
