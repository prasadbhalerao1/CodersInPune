#!/bin/sh
# Restore drill: restore the newest backup into a scratch database and check it.
# Proves backups are usable without touching the live database. Run monthly.
#   sh deploy/restore-drill.sh
set -eu
COMPOSE="docker compose -f deploy/docker-compose.prod.yml"
latest=$($COMPOSE exec -T backup sh -c 'ls -1t /backups/relay-*.dump | head -1')
[ -n "$latest" ] || { echo "no backup found"; exit 1; }
echo "restoring $latest into relay_restore_drill"
$COMPOSE exec -T db psql -U postgres -c "DROP DATABASE IF EXISTS relay_restore_drill" -c "CREATE DATABASE relay_restore_drill"
$COMPOSE exec -T backup sh -c "pg_restore -h db -U postgres -d relay_restore_drill --no-owner --exit-on-error '$latest'"
version=$($COMPOSE exec -T db psql -U postgres -d relay_restore_drill -Atc "SELECT version_num FROM alembic_version")
tenants=$($COMPOSE exec -T db psql -U postgres -d relay_restore_drill -Atc "SELECT count(*) FROM platform.tenant")
echo "restored: schema $version, $tenants workspace(s)"
$COMPOSE exec -T db psql -U postgres -c "DROP DATABASE relay_restore_drill"
echo "restore drill passed"
