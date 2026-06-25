import logging

from django.db import models

logger = logging.getLogger(__name__)


class MailingRecord(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"

    external_id = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
    )
    user_id = models.CharField(max_length=255)
    email = models.EmailField()
    subject = models.TextField(blank=True)
    message = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.external_id} ({self.email})"
