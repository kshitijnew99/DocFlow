from celery import Celery
import ssl
from urllib.parse import urlparse
from app.core.config import get_settings

settings = get_settings()


def _is_secure_redis(url: str) -> bool:
    return urlparse(url).scheme == "rediss"


celery_ssl_config = {}
if _is_secure_redis(settings.CELERY_BROKER_URL):
    celery_ssl_config["broker_use_ssl"] = {"ssl_cert_reqs": ssl.CERT_REQUIRED}
if _is_secure_redis(settings.CELERY_RESULT_BACKEND):
    celery_ssl_config["redis_backend_use_ssl"] = {"ssl_cert_reqs": ssl.CERT_REQUIRED}

celery_app = Celery(
    "docflow",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "app.workers.tasks.process_document": {"queue": "documents"},
    },
    task_default_queue="documents",
    **celery_ssl_config,
)
