#!/bin/sh
set -e
docker exec -w /app/backend buildwatch-public-api-1 python -c "
import db, evaluate
for row in db.query('SELECT id FROM objects'):
    print(row['id'], evaluate.evaluate_object(row['id']))
"
docker exec -w /app/backend buildwatch-public-api-1 python -c "
import db
print('R-07 left:', db.query(\"SELECT COUNT(*) AS n FROM warnings WHERE rule LIKE 'R-07%'\")[0]['n'])
"
