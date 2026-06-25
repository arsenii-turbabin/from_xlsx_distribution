import logging
from random import randint
from time import sleep

from celery import shared_task
from django.db import close_old_connections

from mailing.models import MailingRecord

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def send_email_task(self, record_id: int) -> None:
    """
    Simulates email sending.

    Requirements:
    - delay must be present
    - delivery should happen asynchronously
    """

    close_old_connections()

    record = MailingRecord.objects.get(pk=record_id)

    sleep(randint(5, 20))

    logger.info(
        "EMAIL SENT | id=%s | email=%s | subject=%s",
        record.pk,
        record.email,
        record.subject,
    )

    record.status = MailingRecord.Status.SENT
    record.save(update_fields=["status"])
