# Database recovery

RPO target: 15 minutes. RTO target: 60 minutes. Prove with a restore drill, do not cite until measured.

Embedded:

```text
python scripts/backup.py
python scripts/restore.py --from artifacts/backups/<stamp>
```

Compose/Postgres: `pg_dump` the `tracefix` database, restore into a clean instance, run `alembic upgrade head`, then `python scripts/tf.py verify-staging`.
