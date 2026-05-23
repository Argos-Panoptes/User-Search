cd user-search-code-here

# run docker backing services
cd ..
cd user-search\user-search-code-here
docker compose -f docker-compose-dev.yml down -v
docker compose -f docker-compose-dev.yml up -d

# check container
docker stats

cd user-search\fastapi-google-oauth-demo
uvicorn main:app --reload --port=9000

cd user-search\user-search-code-here\auth
npm run dev

# backend services - fastapi, celery worker, flower observer
# fastapi
cd user-search\user-search-code-here\backend
python -m uvicorn app.main:app --reload
# celery worker
# for windows
cd user-search\user-search-code-here\backend

# Run these in separate terminals:
# Worker 1: Users (concurrency 1)
cd user-search\user-search-code-here\backend
celery -A app.core.celery_app worker --loglevel=info -Q users --concurrency=1 -P gevent -n worker_users@%h
# Worker 2: Groups (concurrency 1)
cd user-search\user-search-code-here\backend
celery -A app.core.celery_app worker --loglevel=info -Q groups --concurrency=1 -P gevent -n worker_groups@%h
# Worker 3: Avatars (concurrency 1)
cd user-search\user-search-code-here\backend
celery -A app.core.celery_app worker --loglevel=info -Q avatars --concurrency=1 -P gevent -n worker_avatars@%h
# Worker 4: Default/Legacy
cd user-search\user-search-code-here\backend
celery -A app.core.celery_app worker --loglevel=info -Q ingestion,celery,reconstruction -P gevent -n worker_default@%h

# OR for simple dev (mixed):
celery -A app.core.celery_app worker --loglevel=info -Q users,groups,avatars,ingestion,celery,reconstruction -P gevent -n worker_mixed@%h
# flower observer
cd user-search\user-search-code-here\backend
celery -A app.core.celery_app flower --port=5555
# celery beat (scheduler)
cd user-search\user-search-code-here\backend
celery -A app.core.celery_app beat --loglevel=info

# frontend
# cd ../frontend/user-search
cd user-search\user-search-code-here\frontend
npm run dev
