import uuid
from django.db import models
from django.conf import settings
from django.contrib.sessions.models import Session


class Main(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class GlobalDefaultQuerySet(models.QuerySet):
    """
    QuerySet that supports filtering by tenant with global default fallback.

    Use with models that have both `tenant_id` and `is_default` fields.
    Returns records that belong to the given tenant OR are marked as global defaults.

    Reusable by:
      - Transfer Reasons
      - Categories / Units / Brands (with global defaults)
      - Workflow Definitions
      - Notification Templates
      - Reservation Reasons
      - Any master data supporting tenant-specific + global default records
    """

    def for_tenant(self, tenant_id):
        """
        Filter to records belonging to the given tenant OR global defaults.

        Usage:
            MyModel.objects.for_tenant(tenant_id)
            MyModel.objects.filter(status='ACTIVE').for_tenant(tenant_id)
        """
        return self.filter(
            models.Q(tenant_id=tenant_id) | models.Q(is_default=True)
        )

    def for_tenant_chain(self, tenant_id, **filters):
        """
        Convenience: filter by tenant + global defaults AND additional filters.

        Usage:
            MyModel.objects.for_tenant_chain(tenant_id, status='ACTIVE')
        """
        qs = self.for_tenant(tenant_id)
        if filters:
            qs = qs.filter(**filters)
        return qs


class GlobalDefaultManager(models.Manager):
    """
    Manager that provides `for_tenant()` to retrieve tenant-specific
    OR global default records in a single query.

    Usage:
        class MyModel(models.Model):
            objects = GlobalDefaultManager()

        MyModel.objects.for_tenant(tenant_id)
        MyModel.objects.for_tenant(tenant_id, status='ACTIVE')
    """

    def get_queryset(self):
        return GlobalDefaultQuerySet(self.model, using=self._db)

    def for_tenant(self, tenant_id):
        """Return records belonging to the tenant OR global defaults."""
        return self.get_queryset().for_tenant(tenant_id)


class UserSession(Main):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    session = models.OneToOneField(Session, on_delete=models.CASCADE)
