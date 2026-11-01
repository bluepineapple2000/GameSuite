from django.db import models


class GenerationGate(models.Model):
    """A database lease bounds AI concurrency across all application threads."""

    available_at = models.DateTimeField()
    token = models.UUIDField(null=True)
