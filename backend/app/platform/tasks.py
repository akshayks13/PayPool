import os

from celery import Celery
from dotenv import load_dotenv

load_dotenv()
app = Celery("paypool", broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"))
app.conf.update(
    task_ignore_result=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    beat_schedule={"paypool-tick": {"task": "paypool.commerce_tick", "schedule": 10.0}},
)


@app.task(
    name="paypool.commerce_tick",
    autoretry_for=(ConnectionError,),
    retry_backoff=True,
    max_retries=3,
)
def commerce_tick():
    from app.platform.worker import tick

    return tick()
