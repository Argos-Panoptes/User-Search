from celery import Celery
from celery.schedules import crontab
from app.core.config import settings

# Create Celery app
celery_app = Celery(
    "ingestion_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_track_started=True,
    worker_send_task_events=True,
    broker_connection_retry_on_startup=True,
    task_ack_late=True,
    task_reject_on_worker_lost=True,
    task_default_delivery_mode="persistent",
    broker_transport_options={
        "visibility_timeout": 43200
    },  # 12 hours visibility timeout for long running tasks
)

# Imports are handled by celery_app.conf.imports to avoid circular dependencies
# from app.tasks import ingestion_tasks, user_tasks, reconstruction

# Initialize Routes - Simple for now, can be expanded like reference
celery_app.conf.task_routes = {
    # Users
    "ingestion_tasks.process_users_step": {"queue": "users"},
    "ingestion_tasks.process_user_data_task": {"queue": "users"},
    # Groups
    "ingestion_tasks.process_groups_step": {"queue": "groups"},
    "ingestion_tasks.process_group_data_task": {"queue": "groups"},
    # Avatars
    "ingestion_tasks.process_avatars_step": {"queue": "avatars"},
    "ingestion_tasks.process_avatar_data_task": {"queue": "avatars"},
    "avatar_sync_tasks.run_avatar_sync_batch": {"queue": "avatars"},
    # Other
    "reconstruction_tasks.reconstruct_group_links_task": {"queue": "reconstruction"},
}

celery_app.conf.imports = [
    "app.tasks.ingestion_tasks",
    "app.tasks.user_tasks",
    "app.tasks.maintenance_tasks",
    "app.tasks.reconstruction",
    "app.tasks.avatar_sync_tasks",
]

celery_app.conf.task_queues = {
    "users": {
        "exchange": "users",
        "routing_key": "users",
    },
    "groups": {
        "exchange": "groups",
        "routing_key": "groups",
    },
    "avatars": {
        "exchange": "avatars",
        "routing_key": "avatars",
    },
    "ingestion": {
        "exchange": "ingestion",
        "routing_key": "ingestion",
    },
    "celery": {
        "exchange": "celery",
        "routing_key": "celery",
    },
}

# Beat Schedule
celery_app.conf.beat_schedule = {
    "trigger-scheduled-link-reconstruction": {
        "task": "reconstruction_tasks.trigger_scheduled_link_reconstruction",
        "schedule": 60.0,  # Run every minute to check if interval has passed
    },
    "daily-database-maintenance": {
        "task": "maintenance_tasks.daily_maintenance",
        "schedule": crontab(hour=3, minute=0),  # Run at 3 AM daily
    },
    "cleanup-stale-uploads": {
        "task": "maintenance_tasks.cleanup_stale_uploads_task",
        "schedule": crontab(hour=4, minute=0),  # Run at 4 AM daily
        "args": (24,),  # Clean folders older than 24 hours
    },
    "trigger-scheduled-avatar-sync": {
        "task": "avatar_sync_tasks.trigger_scheduled_avatar_sync",
        "schedule": crontab(hour=2, minute=30),  # 2:30 AM daily (Part B revalidation)
    },
}
