"""Direct SQL regressions for the version 1 PostgreSQL policy."""

import os
from pathlib import Path
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).parent / "gates"))
from native import Target


@unittest.skipUnless(os.environ.get("DL077_GATE_TARGET"), "requires an owned PostgreSQL fixture")
class PostgresPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.target = Target()
        cls.accept("""
            CREATE ROLE v1_other LOGIN CREATEDB;
            CREATE ROLE v1_noninherited;
            GRANT v1_noninherited TO v1_other WITH INHERIT FALSE, SET TRUE;
            CREATE ROLE v1_copier LOGIN CREATEDB;
            CREATE DATABASE v1_owned OWNER v1_copier TEMPLATE template0;
            GRANT CONNECT ON DATABASE v1_owned TO v1_other;
            CREATE ROLE megasamples_copy_v1_owner;
            GRANT megasamples_copy_v1_owner TO v1_copier WITH INHERIT TRUE, SET FALSE;
            CREATE DATABASE v1seed_start TEMPLATE template0 IS_TEMPLATE true ALLOW_CONNECTIONS false;
            COMMENT ON DATABASE v1seed_start IS 'megasamples-template/1 {"database":"v1seed"}';
            CREATE DATABASE v1unregistered_start TEMPLATE template0 IS_TEMPLATE true ALLOW_CONNECTIONS false;
            CREATE ROLE v1_readonly LOGIN;
        """)
        cls.accept("""
            CREATE SCHEMA v1_shadow;
            CREATE TABLE v1_shadow.pg_roles (rolname name, oid oid);
            CREATE TABLE v1_shadow.pg_database (datname name, oid oid);
            CREATE FUNCTION v1_shadow.pg_has_role(oid, oid, text) RETURNS boolean
            LANGUAGE sql AS 'SELECT false';
        """, "v1_copier", "v1_owned")

    @classmethod
    def sql(cls, statement, user="postgres", database="postgres"):
        return subprocess.run(
            cls.target.podman_args(*cls.target.psql_args(database, user)),
            input=statement + "\n", text=True, capture_output=True, timeout=60,
        )

    @classmethod
    def accept(cls, statement, user="postgres", database="postgres"):
        result = cls.sql(statement, user, database)
        if result.returncode:
            raise AssertionError(result.stderr.strip())
        return result.stdout.strip()

    def refuse(self, statement, user, database="postgres", code="42501"):
        result = self.sql(statement, user, database)
        self.assertNotEqual(result.returncode, 0, "statement unexpectedly succeeded")
        self.assertIn(code, result.stderr)

    def refuse_create(self, name, options, database, search_path):
        result = self.sql(f"SET search_path={search_path};\nCREATE DATABASE {name} {options}",
                          "v1_copier", database)
        if result.returncode == 0:
            self.accept(f"DROP DATABASE {name}")
        self.assertNotEqual(result.returncode, 0, "statement unexpectedly succeeded")
        self.assertIn("42501", result.stderr)

    def test_creator_must_inherit_the_new_owners_rights(self):
        self.refuse("CREATE DATABASE v1_owner_refused OWNER v1_noninherited", "v1_other")
        self.assertEqual(self.accept("SELECT count(*) FROM pg_database WHERE datname='v1_owner_refused'"), "0")
        self.accept("GRANT v1_noninherited TO v1_other WITH INHERIT TRUE")
        try:
            self.accept("CREATE DATABASE v1_owner_allowed OWNER v1_noninherited", "v1_other")
        finally:
            self.accept("REVOKE v1_noninherited FROM v1_other")

    def test_namespace_destination_source_and_rename(self):
        for database, search_path in [("megasamples", "public"), ("v1_owned", "v1_shadow, pg_catalog")]:
            with self.subTest(database=database):
                def command(sql):
                    return f"SET search_path={search_path};\n{sql}"

                for bad in ("other_v1seed_123456789abc", "v1_v1seed_123456789ab",
                            "v1_v1seed_123456789abcd", '"v1_v1seed_123456789abé"',
                            "v1_another_123456789abc"):
                    with self.subTest(destination=bad):
                        self.refuse_create(bad, "TEMPLATE v1seed_start", database, search_path)
                for source in ("template0", "template1", "v1unregistered_start"):
                    with self.subTest(source=source):
                        self.refuse_create("v1_v1seed_123456789abc", f"TEMPLATE {source}", database, search_path)
                self.accept(command("CREATE DATABASE v1_v1seed_123456789abc TEMPLATE v1seed_start"),
                            "v1_copier", database)
                try:
                    self.refuse(command("ALTER DATABASE v1_v1seed_123456789abc RENAME TO v1_other_name"),
                                "v1_copier", database)
                finally:
                    self.accept("DROP DATABASE IF EXISTS v1_v1seed_123456789abc")
                    self.accept("DROP DATABASE IF EXISTS v1_other_name")
                self.accept(command("CREATE DATABASE v1_v1seed_123456789abc"), "v1_other", database)
                self.accept(command("ALTER DATABASE v1_v1seed_123456789abc RENAME TO v1_free_name"),
                            "v1_other", database)
                self.accept("DROP DATABASE v1_free_name", "v1_other")

    def test_new_database_closes_public_in_the_creating_command(self):
        self.accept("CREATE DATABASE v1_closed", "v1_other")
        privileges = self.accept("""
            SELECT has_database_privilege('v1_readonly','v1_closed','CONNECT'),
                   has_database_privilege('v1_readonly','v1_closed','TEMP'),
                   has_database_privilege('v1_other','v1_closed','CONNECT'),
                   has_database_privilege('v1_other','v1_closed','TEMP');
        """)
        self.assertEqual(privileges, "f|f|t|t")
        result = self.sql("SELECT 42", "v1_readonly", "v1_closed")
        self.assertIn("permission denied for database", result.stderr)

    def test_create_keeps_catalog_and_files_consistent_when_admin_is_absent(self):
        def orphan_count():
            return self.accept("""
                SELECT count(*) FROM pg_ls_dir('base') AS entries(entry)
                WHERE entry ~ '^[0-9]+$'
                AND NOT EXISTS (SELECT FROM pg_database WHERE oid::text=entry)
            """)

        before = orphan_count()
        self.accept("ALTER ROLE admin RENAME TO v1_saved_admin")
        try:
            created = self.sql("CREATE DATABASE v1_no_admin TEMPLATE template0")
            self.assertEqual(orphan_count(), before, "failed policy left an orphaned database directory")
            self.assertEqual(created.returncode, 0, created.stderr)
            result = self.sql("SELECT 42", "v1_readonly", "v1_no_admin")
            self.assertIn("permission denied for database", result.stderr)
        finally:
            self.accept("ALTER ROLE v1_saved_admin RENAME TO admin")

    def test_role_and_default_privilege_alterations_require_createrole(self):
        for user in ("demo", "v1_readonly", "v1_copier", "v1_other"):
            for statement in ("ALTER ROLE CURRENT_USER PASSWORD NULL",
                              "ALTER ROLE CURRENT_USER SET statement_timeout = '60s'",
                              "ALTER DEFAULT PRIVILEGES REVOKE EXECUTE ON ROUTINES FROM PUBLIC"):
                with self.subTest(user=user, statement=statement):
                    self.refuse(statement, user)
            self.assertEqual(self.accept("SELECT 42", user), "42")
        self.accept("ALTER ROLE CURRENT_USER SET statement_timeout TO DEFAULT", "admin")

    @unittest.skipUnless(os.environ.get("DL077_PG_CLOSE_FAULT"), "requires a planted ACL fault")
    def test_close_fallback_keeps_the_database_and_disables_connections(self):
        self.accept("CREATE DATABASE v1_closure_fault", "v1_other")
        self.assertEqual(self.accept("""
            SELECT datallowconn, (pg_stat_file('base/' || oid)).isdir
            FROM pg_database WHERE datname='v1_closure_fault'
        """), "f|t")
        for user in ("v1_other", "v1_readonly"):
            result = self.sql("SELECT 42", user, "v1_closure_fault")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("not currently accepting connections", result.stderr)

    def test_fresh_roles_get_expression_and_snapshot_floor(self):
        for user in ("v1_readonly", "v1_copier", "v1_other", "demo"):
            with self.subTest(user=user):
                self.assertEqual(self.accept("SELECT 1 = 1", user, "megasamples"), "t")
                self.assertEqual(self.accept("""
                    BEGIN READ ONLY;
                    SELECT pg_current_snapshot() IS NOT NULL,
                           pg_export_snapshot() IS NOT NULL,
                           pg_database_size((SELECT oid FROM pg_database WHERE datname=current_database())) > 0;
                    ROLLBACK;
                """, user, "megasamples"), "t|t|t")
                self.refuse("SELECT pg_current_xact_id()", user, "megasamples")
                self.refuse("SELECT lo_create(0)", user, "megasamples")

    def test_fixture_roles_inherit_no_working_access_and_get_explicit_fixture_grants(self):
        self.accept("""
            CREATE ROLE di_reader LOGIN;
            CREATE ROLE di_analyst LOGIN;
            GRANT di_reader, di_analyst TO CURRENT_USER WITH INHERIT TRUE, SET FALSE;
            CREATE DATABASE di_native TEMPLATE template0;
            GRANT CONNECT ON DATABASE di_native TO di_reader, di_analyst;
        """, "admin")
        self.accept("""
            CREATE FUNCTION public.v1_read() RETURNS int LANGUAGE sql AS 'SELECT 42';
            GRANT EXECUTE ON FUNCTION public.v1_read() TO di_reader;
            GRANT TEMPORARY ON DATABASE di_native TO di_analyst;
        """, "admin", "di_native")
        self.assertEqual(self.accept("SELECT 1 = 1, public.v1_read()", "di_reader", "di_native"), "t|42")
        self.refuse("SELECT public.v1_read()", "di_analyst", "di_native")
        self.refuse("CREATE TEMP TABLE v1_t(i int)", "di_reader", "di_native")
        self.accept("CREATE TEMP TABLE v1_t(i int)", "di_analyst", "di_native")
        for user in ("di_reader", "di_analyst"):
            self.refuse("ALTER ROLE CURRENT_USER PASSWORD NULL", user, "di_native")
            result = self.sql("SELECT 42", user, "chinook")
            self.assertIn("permission denied for database", result.stderr)

    def test_event_trigger_closes_routines_without_a_role_named_admin(self):
        self.accept("ALTER ROLE admin RENAME TO v1_saved_admin")
        try:
            self.accept("CREATE FUNCTION public.v1_new() RETURNS int LANGUAGE sql AS 'SELECT 42'",
                        "v1_copier", "v1_owned")
            self.assertEqual(self.accept("""
                SELECT count(*) FROM pg_proc p,
                    aclexplode(coalesce(p.proacl, acldefault('f',p.proowner))) acl
                WHERE p.oid='public.v1_new()'::regprocedure AND acl.grantee=0
            """, database="v1_owned"), "0")
        finally:
            self.accept("ALTER ROLE v1_saved_admin RENAME TO admin")

    @unittest.skipUnless(os.environ.get("DL077_PG_IMAGE_TEMPLATES"), "requires a built template selection")
    def test_image_template_is_registered_closed_and_held_by_postgres(self):
        self.assertEqual(self.accept("""
            SELECT datistemplate, datallowconn, pg_get_userbyid(datdba)
            FROM pg_database WHERE datname='chinook_start'
        """), "t|f|postgres")
        registration = self.accept("""
            SELECT shobj_description(oid, 'pg_database')
            FROM pg_database WHERE datname='chinook_start'
        """)
        self.assertTrue(registration.startswith("megasamples-template/1 {"))
        for role in ("postgres", "admin", "demo", "v1_readonly", "v1_copier"):
            with self.subTest(role=role):
                result = self.sql("SELECT 1", role, "chinook_start")
                self.assertIn("not currently accepting connections", result.stderr)
        self.refuse("ALTER DATABASE chinook_start ALLOW_CONNECTIONS true", "admin")
        self.accept("CREATE DATABASE copy_chinook_000000000000 TEMPLATE chinook_start", "copier")
        self.assertGreater(int(self.accept("SELECT count(*) FROM album", "copier",
                                         "copy_chinook_000000000000")), 0)
        self.accept("BEGIN; UPDATE album SET title='isolated edit'; ROLLBACK",
                    "copier", "copy_chinook_000000000000")
        self.assertGreater(int(self.accept("SELECT count(*) FROM album", "demo", "chinook")), 0)

    def test_working_writer_has_the_writer_routine_list(self):
        self.accept("CREATE ROLE v1_writer LOGIN")
        self.accept("""
            CREATE SEQUENCE v1_seq;
            CREATE TABLE v1_writes (value bigint);
            CREATE FUNCTION v1_fill() RETURNS trigger LANGUAGE plpgsql AS
                'BEGIN NEW.value := nextval(''v1_seq''); RETURN NEW; END';
            CREATE TRIGGER v1_fill BEFORE INSERT ON v1_writes FOR EACH ROW EXECUTE FUNCTION v1_fill();
        """, "admin", "chinook")
        self.assertEqual(self.accept("""
            SELECT coalesce(pg_has_role('v1_writer', to_regrole('megasamples_working_write'), 'MEMBER'), false)
        """), "f")
        self.accept("GRANT megasamples_working_write TO v1_writer WITH INHERIT TRUE, SET FALSE")
        self.accept("GRANT USAGE ON SEQUENCE v1_seq TO v1_writer", "admin", "chinook")
        self.assertEqual(self.accept("INSERT INTO v1_writes DEFAULT VALUES RETURNING value",
                                     "v1_writer", "chinook"), "1")
        self.refuse("SELECT lo_create(0)", "v1_writer", "chinook")
        self.refuse("CREATE TABLE v1_not_allowed (id int)", "v1_writer", "chinook")


if __name__ == "__main__":
    unittest.main()
