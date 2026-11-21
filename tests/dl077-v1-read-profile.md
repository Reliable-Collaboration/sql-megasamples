# DL-077 slice 1 evidence

The direct SQL tests use a disposable, labeled target in the isolated store. The build included `chinook`, `pubs`, `sakila`, `adventureworks_lt` and `jaffle_shop`. The red image used PR #14's policy. The green image used the four corrected rules and the updated grants.

| Design claim | Direct SQL regression | Red | Green | Reversal |
|---|---|---|---|---|
| 4.3 rule 1 | `test_creator_must_inherit_the_new_owners_rights` | Creator with SET and no INHERIT succeeded | Failed with 42501, then passed with INHERIT | Removing the rights check allowed creation |
| 4.3 rule 2 | `test_namespace_destination_source_and_rename` | Forbidden commands succeeded | Boundary held from the registry and the owner's database | Removing confinement allowed forbidden commands |
| 4.3 rule 3 | `test_new_database_closes_public_in_the_creating_command` | Another login had CONNECT | CONNECT and TEMP were closed to PUBLIC | Omitting the ACL update exposed both privileges |
| 4.3 H-3 | `test_create_keeps_catalog_and_files_consistent_when_admin_is_absent`, `test_close_fallback_keeps_the_database_and_disables_connections` | A post-copy role lookup left a directory without a catalog row | Normal create passed. Omitting the ACL write or forcing confirmation to fail left a cataloged database with connections disabled | Moving an error after the physical copy left a directory. Omitting the fallback after the skipped write let the database accept connections |
| 4.3 rule 4 | `test_role_and_default_privilege_alterations_require_createrole` | The restricted ALTER statements succeeded | All restricted role changes were refused. Admin could still change its settings | Omitting the rule allowed the statements |
| 4.2 P-1, P-3 | `test_fresh_roles_get_expression_and_snapshot_floor` | Fresh roles lacked the operator function. Demo lacked the snapshot routine | All named roles read and could call the three built-ins | PR #14's demo-only grant and missing routines were observed on the red image |
| 4.2 P-6 | `test_working_writer_has_the_writer_routine_list` | No working writer group existed | Working writer advanced a sequence through a trigger and was refused DDL and large-object creation | Full candidate write-list reversal pending |
| 4.3 H-9 | `test_event_trigger_closes_routines_without_a_role_named_admin` | Creating the routine failed with missing role | Routine creation succeeded with PUBLIC closed | Presence of the failing lookup observed on the red image |
| 7.2 fixture roles | `test_fixture_roles_inherit_no_working_access_and_get_explicit_fixture_grants` | Fixture reader lacked the operator function | Explicit fixture routine and TEMP grants worked. Fixture logins were refused working-database connections and self-password changes | Candidate-specific reversal pending |

The [candidate catalog inventory](../docs/validation/dl-077-v1-public-routines.md) ([JSON](../docs/validation/dl-077-v1-public-routines.json)) was queried as superuser for every routine `demo` can execute, in each of the candidate's 6 connectable databases, on image `cf7325f4f9be` at 2026-11-21 11:57:55 UTC (`docs/validation/dl077-public-routines.py`). That is `demo`'s own set: it includes one routine granted to `demo` directly, so a new login does not hold all of it. The set was compared, signature by signature, with DataIntent's IA-01 inventory at `4a8aad61c8ab140e71155e707fba328a7a647707`, read 2026-11-21 11:58:14 UTC. Its SHA-256, `be570f39…8076`, matches its source receipt and PR #14's inventory, which is retained unchanged at [its path](../docs/validation/strict-read-executable-routines.md) as that PR's evidence. IA-01 has 1,663 signatures and the candidate 1,667: four additions, no removals, and no changed reason, namespace, kind or volatility on the 1,663 in both.

| Change | Signature | Disposition |
|---|---|---|
| Added | `pg_current_snapshot()` | `PUBLIC` floor, design 4.2 P-3: returns the current snapshot without assigning a transaction ID |
| Added | `pg_database_size(oid)` | `PUBLIC` floor, design 4.2 P-3: reads a database's size with the caller's existing access |
| Added | `pg_export_snapshot()` | `PUBLIC` floor, design 4.2 P-3 and P-5: publishes a snapshot another session can import while the exporting transaction lives |
| Added | `megasamples_policy_loaded()` | A direct grant to `demo`, outside `PUBLIC`, design 4.2 P-8: the healthcheck's report that the `read_policy` library was preloaded. Revoked from `PUBLIC` and `admin` |

The receipt hashes of PR #14's publication canary scan describe that PR's head, `2879fc472ad1`. Version 1 changed on purpose twelve of the files it hashed: the strict-read guide, `.dockerignore`, the PostgreSQL Dockerfile, read profile, routine names and the read_policy extension's SQL, C and control files, both image tests, the MySQL image startup test and the native suite. Their hashes in the receipt are of `2879fc472ad1`; `tests/test_v1_public_routines.py` names the twelve and requires every other file the receipt hashed to match it. The round 8 class check (`tests/dl077-v1-loop.md`) found no other evidence file a version 1 change overwrote.

This evidence covers the candidate checks above. Independent hook and event-trigger review, DataIntent's C1 comparison and the complete image and dataset matrices remain pending.
