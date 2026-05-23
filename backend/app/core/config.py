from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    PROJECT_NAME: str = "User Search"
    API_V1_STR: str = "/api/v1"

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]
    FRONTEND_URL: str = "http://localhost:5173"

    # Database & Search
    DATABASE_URL: str = "postgresql://postgres:postgres@db:5432/user_search"
    DB_POOL_SIZE: int = 5
    OPENSEARCH_URL: str = "http://opensearch:9200"
    REDIS_URL: str = "redis://redis:6379/0"

    # Message Broker (Celery/RabbitMQ)
    CELERY_BROKER_URL: str = "amqp://guest:guest@rabbitmq:5672//"

    # Auth
    ENABLE_AUTH: bool = True
    JWT_SECRET_KEY: str = "super_secret_key_change_me"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 1 week
    AUTH_COOKIE_NAME: str = "better-auth.session_token"
    BETTER_AUTH_SECRET: str = ""

    # Spark
    SPARK_MASTER_URL: str = "spark://spark-master:7077"  # Default to docker cluster

    # Data & Uploads
    EXPORT_DATA_DIR: str = "export_data"
    UPLOAD_TEMP_DIR_NAME: str = "temp_uploads"
    UPLOAD_FINAL_DIR_NAME: str = "uploads"

    # Stripe
    STRIPE_API_KEY: str = ""
    STRIPE_PUBLISHABLE_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PRICE_ID: str = ""
    STRIPE_TRIAL_PERIOD_DAYS: int = 0

    # Roles
    ADMIN_EMAIL_DOMAIN: str = "red-wing.io"

    # Job Intervals
    LINK_RECONSTRUCTION_INTERVAL_MINUTES: int = 15  # Default 15 minutes

    # S3 (for avatar storage - optional, falls back to local filesystem)
    S3_BUCKET_NAME: str = ""
    S3_ENDPOINT_URL: str = ""
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_REGION: str = "us-east-1"

    # Local avatar storage (used when S3 is not configured)
    AVATAR_LOCAL_DIR: str = "data/avatars"

    # Avatar Sync (Part B - Scheduled Revalidation)
    AVATAR_SYNC_ENABLED: bool = False  # Kill switch, off by default until tested
    AVATAR_SYNC_INTERVAL_HOURS: int = 24  # How often to run (daily)
    AVATAR_SYNC_BATCH_SIZE: int = 100  # Avatars per batch
    AVATAR_SYNC_BATCH_DELAY_SECONDS: int = 2  # Delay between batches (rate limiting + queue fairness)
    AVATAR_SYNC_MAX_RETRIES: int = 2  # Per-batch Celery retry limit
    # Signal CDN Fetch Settings
    AVATAR_SYNC_CDN_BASE_URL: str = "https://cdn.signal.org/"
    AVATAR_SYNC_CDN_TIMEOUT: int = 15  # CDN HTTP request timeout in seconds
    AVATAR_SYNC_CDN_REQUESTS_PER_SEC: int = 10  # Conservative for external CDN
    AVATAR_SYNC_CDN_VERIFY_SSL: bool = False  # Signal CDN requires verify=False (their cert chain causes timeouts)

    # Smart Filtering (TTL-based checks by change frequency)
    AVATAR_SYNC_CHECK_HIGH_FREQ_HOURS: int = 6  # Re-check HIGH-change avatars every 6h
    AVATAR_SYNC_CHECK_MEDIUM_FREQ_HOURS: int = 72  # Re-check MEDIUM-change avatars every 3 days
    AVATAR_SYNC_CHECK_LOW_FREQ_HOURS: int = 168  # Re-check LOW-change avatars every 7 days
    AVATAR_SYNC_CHECK_NEVER_VERIFIED_HOURS: int = 24  # Always check never-verified within 24h

    # Rate Limiting & Retry
    AVATAR_SYNC_RETRY_BACKOFF_BASE: float = 0.5  # Backoff: 0.5s, 1s

    # Timeout & Alerting
    AVATAR_SYNC_TIMEOUT_SECONDS: int = 3600  # Hard 1-hour limit per run
    AVATAR_SYNC_ALERT_IF_EXCEEDS_SECONDS: int = 1800  # Log warning if runs > 30 min

    # Parallelism & Sharding
    AVATAR_SYNC_SHARD_COUNT: int = 4  # Number of ID-range shards for parallel dispatch
    AVATAR_SYNC_THREAD_POOL_SIZE: int = 16  # Max concurrent CDN fetch threads per batch

    # SSIM Visual Similarity (0.0=completely different, 1.0=identical)
    AVATAR_SYNC_SSIM_THRESHOLD: float = 0.9  

    # Whitelist
    WHITELISTED_DOMAINS: list[str] = ["red-wing.io", "itsyourgov.org"]

    # Public API
    API_VERSION: str = "1.0.0"
    DATA_VERSION: str = "1.0.0"
    RATE_LIMIT_REDIS_URL: str = "redis://redis:6379/1"
    MAX_API_KEYS_PER_USER: int = 5
    DEFAULT_API_KEY_QUOTA: int = 100  # requests per minute for user-created keys

    class Config:
        env_file = ".env"


settings = Settings()
