/*
 * Check creator and namespace privileges before cloning. PostgreSQL calls
 * OAT_POST_CREATE for the new catalog row before copying any database files.
 */
#include "postgres.h"

#include "access/genam.h"
#include "access/htup_details.h"
#include "access/table.h"
#include "access/xact.h"
#include "catalog/indexing.h"
#include "catalog/objectaccess.h"
#include "catalog/pg_authid.h"
#include "catalog/pg_database.h"
#include "catalog/pg_shdescription.h"
#include "commands/dbcommands.h"
#include "commands/defrem.h"
#include "fmgr.h"
#include "miscadmin.h"
#include "storage/lmgr.h"
#include "tcop/utility.h"
#include "utils/acl.h"
#include "utils/builtins.h"
#include "utils/fmgroids.h"
#include "utils/syscache.h"

PG_MODULE_MAGIC;
void _PG_init(void);

static ProcessUtility_hook_type previous_utility;
static object_access_hook_type previous_object_access;

static bool
has_template_tag(Oid oid)
{
    const char *tag = "megasamples-template/1 {";
    ScanKeyData keys[2];
    Relation relation;
    SysScanDesc scan;
    HeapTuple tuple;
    bool matches = false;

    ScanKeyInit(&keys[0], Anum_pg_shdescription_objoid,
                BTEqualStrategyNumber, F_OIDEQ, ObjectIdGetDatum(oid));
    ScanKeyInit(&keys[1], Anum_pg_shdescription_classoid,
                BTEqualStrategyNumber, F_OIDEQ, ObjectIdGetDatum(DatabaseRelationId));
    relation = table_open(SharedDescriptionRelationId, AccessShareLock);
    scan = systable_beginscan(relation, SharedDescriptionObjIndexId, true, NULL, 2, keys);
    tuple = systable_getnext(scan);
    if (HeapTupleIsValid(tuple))
    {
        bool isnull;
        Datum value = heap_getattr(tuple, Anum_pg_shdescription_description,
                                  RelationGetDescr(relation), &isnull);

        if (!isnull)
        {
            char *comment = TextDatumGetCString(value);

            matches = strncmp(comment, tag, strlen(tag)) == 0;
            pfree(comment);
        }
    }
    systable_endscan(scan);
    table_close(relation, AccessShareLock);
    return matches;
}

static bool
registered_template(const char *name)
{
    Oid oid = get_database_oid(name, true);
    HeapTuple tuple;
    bool matches = false;

    if (!OidIsValid(oid))
        return false;

    /* Match the core CREATE DATABASE source lock and recheck by OID. */
    LockSharedObject(DatabaseRelationId, oid, 0, ShareLock);
    tuple = SearchSysCache1(DATABASEOID, ObjectIdGetDatum(oid));
    if (HeapTupleIsValid(tuple))
    {
        Form_pg_database db = (Form_pg_database) GETSTRUCT(tuple);

        matches = strcmp(NameStr(db->datname), name) == 0 &&
                  db->datistemplate && !db->datallowconn &&
                  superuser_arg(db->datdba) && has_template_tag(oid);
        ReleaseSysCache(tuple);
    }
    return matches;
}

static bool
copy_name_matches(const char *name, const char *prefix, size_t prefix_length,
                  const char *source, size_t database_length)
{
    const char *token;

    if (strlen(name) != prefix_length + database_length + 14 ||
        strncmp(name, prefix, prefix_length) != 0 ||
        name[prefix_length] != '_' ||
        strncmp(name + prefix_length + 1, source, database_length) != 0 ||
        name[prefix_length + 1 + database_length] != '_')
        return false;
    token = name + prefix_length + database_length + 2;
    return strspn(token, "0123456789abcdef") == 12;
}

static void
check_namespace(Node *stmt)
{
    static const char marker_prefix[] = "megasamples_copy_";
    static const char marker_suffix[] = "_owner";
    static const char template_suffix[] = "_start";
    const size_t prefix_length = sizeof(marker_prefix) - 1;
    const size_t suffix_length = sizeof(marker_suffix) - 1;
    const size_t template_suffix_length = sizeof(template_suffix) - 1;
    const char *source = "template1";
    const char *destination = NULL;
    size_t database_length = 0;
    Relation roles;
    SysScanDesc scan;
    HeapTuple tuple;
    bool is_owner = false;
    bool matches_destination = false;

    if (IsA(stmt, CreatedbStmt))
    {
        CreatedbStmt *create = castNode(CreatedbStmt, stmt);
        ListCell *cell;
        size_t source_length;

        destination = create->dbname;
        foreach(cell, create->options)
        {
            DefElem *option = lfirst_node(DefElem, cell);

            if (strcmp(option->defname, "template") == 0 && option->arg)
                source = defGetString(option);
        }
        source_length = strlen(source);
        if (source_length > template_suffix_length &&
            strcmp(source + source_length - template_suffix_length, template_suffix) == 0)
            database_length = source_length - template_suffix_length;
    }

    roles = table_open(AuthIdRelationId, AccessShareLock);
    scan = systable_beginscan(roles, InvalidOid, false, NULL, 0, NULL);
    while (HeapTupleIsValid(tuple = systable_getnext(scan)))
    {
        Form_pg_authid role = (Form_pg_authid) GETSTRUCT(tuple);
        const char *name = NameStr(role->rolname);
        size_t length = strlen(name);

        if (length <= prefix_length + suffix_length ||
            strncmp(name, marker_prefix, prefix_length) != 0 ||
            strcmp(name + length - suffix_length, marker_suffix) != 0 ||
            !is_member_of_role(GetUserId(), role->oid))
            continue;
        is_owner = true;
        if (destination && database_length &&
            copy_name_matches(destination, name + prefix_length, length - prefix_length - suffix_length,
                              source, database_length))
            matches_destination = true;
    }
    systable_endscan(scan);
    table_close(roles, AccessShareLock);

    if (!is_owner)
        return;
    if (!destination)
        ereport(ERROR, (errcode(ERRCODE_INSUFFICIENT_PRIVILEGE),
                        errmsg("namespace owners cannot rename databases")));
    if (!database_length || !registered_template(source))
        ereport(ERROR, (errcode(ERRCODE_INSUFFICIENT_PRIVILEGE),
                        errmsg("namespace owners must create databases from registered templates")));
    if (!matches_destination)
        ereport(ERROR, (errcode(ERRCODE_INSUFFICIENT_PRIVILEGE),
                        errmsg("database name does not match the namespace and template")));
}

static bool
public_is_closed(HeapTuple tuple)
{
    bool isnull;
    Datum value = SysCacheGetAttr(DATABASEOID, tuple, Anum_pg_database_datacl, &isnull);
    Acl *acl;

    if (isnull)
        return false;
    acl = DatumGetAclP(value);
    for (int index = 0; index < ACL_NUM(acl); index++)
    {
        AclItem *item = &ACL_DAT(acl)[index];

        if (item->ai_grantee == ACL_ID_PUBLIC &&
            (ACLITEM_GET_PRIVS(*item) & (ACL_CREATE_TEMP | ACL_CONNECT)))
            return false;
    }
    return true;
}

static void
secure_new_database(Oid oid)
{
    Relation relation;
    HeapTuple tuple;
    HeapTuple updated;
    Form_pg_database db;
    Acl *defaults;
    Acl *acl;
    AclItem remove;
    Datum values[Natts_pg_database] = {0};
    bool nulls[Natts_pg_database] = {false};
    bool replace[Natts_pg_database] = {false};

    CommandCounterIncrement();
    tuple = SearchSysCache1(DATABASEOID, ObjectIdGetDatum(oid));
    if (!HeapTupleIsValid(tuple))
        elog(ERROR, "new database catalog row is missing");
    db = (Form_pg_database) GETSTRUCT(tuple);
    if (!has_privs_of_role(GetUserId(), db->datdba))
        ereport(ERROR, (errcode(ERRCODE_INSUFFICIENT_PRIVILEGE),
                        errmsg("the creator must inherit the new database owner's rights")));

    /* Only the owner and PUBLIC can occur in the core's initial ACL. */
    relation = table_open(DatabaseRelationId, RowExclusiveLock);
    defaults = acldefault(OBJECT_DATABASE, db->datdba);
    remove.ai_grantee = ACL_ID_PUBLIC;
    remove.ai_grantor = db->datdba;
    ACLITEM_SET_PRIVS_GOPTIONS(remove, ACL_CONNECT | ACL_CREATE_TEMP, 0);
    acl = aclupdate(defaults, &remove, ACL_MODECHG_DEL, db->datdba, DROP_RESTRICT);
    values[Anum_pg_database_datacl - 1] = PointerGetDatum(acl);
    replace[Anum_pg_database_datacl - 1] = true;
    updated = heap_modify_tuple(tuple, RelationGetDescr(relation), values, nulls, replace);
    CatalogTupleUpdate(relation, &tuple->t_self, updated);
    heap_freetuple(updated);
    ReleaseSysCache(tuple);
    pfree(acl);
    pfree(defaults);

    CommandCounterIncrement();
    tuple = SearchSysCache1(DATABASEOID, ObjectIdGetDatum(oid));
    if (!HeapTupleIsValid(tuple))
        elog(ERROR, "new database catalog row is missing");
    if (!public_is_closed(tuple))
    {
        Form_pg_database closed = (Form_pg_database) GETSTRUCT(tuple);

        replace[Anum_pg_database_datacl - 1] = false;
        replace[Anum_pg_database_datallowconn - 1] = true;
        values[Anum_pg_database_datallowconn - 1] = BoolGetDatum(false);
        updated = heap_modify_tuple(tuple, RelationGetDescr(relation), values, nulls, replace);
        CatalogTupleUpdate(relation, &tuple->t_self, updated);
        heap_freetuple(updated);
        ereport(WARNING, (errmsg("database \"%s\" has been closed to all connections",
                                NameStr(closed->datname))));
    }
    ReleaseSysCache(tuple);
    table_close(relation, NoLock);
}

static void
read_policy_object_access(ObjectAccessType access, Oid classid, Oid objectid,
                          int subid, void *arg)
{
    if (previous_object_access)
        previous_object_access(access, classid, objectid, subid, arg);
    if (access == OAT_POST_CREATE && classid == DatabaseRelationId)
        secure_new_database(objectid);
}

static void
read_policy_utility(PlannedStmt *pstmt, const char *query, bool read_only,
                    ProcessUtilityContext context, ParamListInfo params,
                    QueryEnvironment *env, DestReceiver *dest, QueryCompletion *qc)
{
    Node *stmt = pstmt->utilityStmt;

    if (!superuser())
    {
        if ((IsA(stmt, AlterRoleStmt) || IsA(stmt, AlterRoleSetStmt) ||
             IsA(stmt, AlterDefaultPrivilegesStmt)) && !has_createrole_privilege(GetUserId()))
            ereport(ERROR, (errcode(ERRCODE_INSUFFICIENT_PRIVILEGE),
                            errmsg("altering roles or default privileges requires CREATEROLE")));

        if (IsA(stmt, CreatedbStmt) ||
            (IsA(stmt, RenameStmt) && castNode(RenameStmt, stmt)->renameType == OBJECT_DATABASE))
            check_namespace(stmt);
    }

    if (previous_utility)
        previous_utility(pstmt, query, read_only, context, params, env, dest, qc);
    else
        standard_ProcessUtility(pstmt, query, read_only, context, params, env, dest, qc);
}

void
_PG_init(void)
{
    previous_utility = ProcessUtility_hook;
    ProcessUtility_hook = read_policy_utility;
    previous_object_access = object_access_hook;
    object_access_hook = read_policy_object_access;
}
