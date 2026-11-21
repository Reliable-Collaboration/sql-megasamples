# DL-077 slice 2 evidence

| Design claim | Entry point | Red | Green and controls |
|---|---|---|---|
| 2.3, PostgreSQL template closure, ownership and registration | `megasamples image --engine postgres --keep chinook`, then `test_image_template_is_registered_closed_and_held_by_postgres` over direct SQL | The existing candidate returned no template catalog row | The baked template rejects every tested connection. Admin cannot open it. The baked namespace owner can clone and edit the clone. The working database stays readable by demo |
| 2.2–2.3, PostgreSQL copy commands, proof and leases | `test_postgres_copy_lifecycle_on_tcp` invokes `megasamples copy` with a private password file against a disposable server | Create returned 4 because the CLI had no PostgreSQL copy path | All seven commands ran. The test checked the catalog proof, lookup by label, lease expiry, dry-run, sweep and the busy drop that preserves a session. The disposable volume record was provisioned locally |
| 2.5–2.6, SQLite template manifest | `megasamples image --engine sqlite --keep chinook` and a CLI create using its generated manifest | The old image build exited 0 and wrote no manifest | The staged template was mode 0444, and the CLI created a copy using the recorded SHA-256 |
| 2.1, 2.2, 2.5 and 3.2–3.6, SQLite copy commands | `test_v1_sqlite_copy.py` drives the CLI | 14 cases failed because `copy` was unknown and its JSON was absent | 14 passed. Removing the digest comparison, identity guard, lease check, namespace limit or label validation each failed a targeted test |

Coverage still due includes the MySQL build and lifecycle, candidate-specific PostgreSQL copy reversals, the kill-point and disk-full matrices, and the cross-command and account/database matrices. The PostgreSQL copy CLI requires a qualified service volume record. Test fixtures supply that record while the start and reset integration remains deferred.
