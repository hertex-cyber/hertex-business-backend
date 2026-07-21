from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Prefetch
from contacts.models import (
    Contact,
    ImportBatch,
    ContactLog,
    ContactRemark,
    ContactDocument,
)
from contacts.serializers import (
    ContactListSerializer,
    ContactSerializer,
    ImportBatchSerializer,
    ContactLogSerializer,
    ContactRemarkSerializer,
    ContactDocumentSerializer,
)
from crm.models import CRM


class ImportBatchViewSet(viewsets.ModelViewSet):
    """List, retrieve, and delete import batches."""

    queryset = ImportBatch.objects.all()
    serializer_class = ImportBatchSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_destroy(self, instance):
        qs = Contact.objects.filter(import_batch=instance)
        ids = list(qs.values_list("id", flat=True))
        for i in range(0, len(ids), 500):
            Contact.objects.filter(id__in=ids[i : i + 500]).delete()
        instance.delete()

    @action(detail=True, methods=["post"], url_path="delete-chunk")
    def delete_chunk(self, request, pk=None):
        batch = self.get_object()
        limit = int(request.data.get("limit", 1500))

        total = Contact.objects.filter(import_batch=batch).count()
        ids = list(
            Contact.objects.filter(import_batch=batch)
            .order_by("id")
            .values_list("id", flat=True)[:limit]
        )

        Contact.objects.filter(id__in=ids).delete()

        remaining = Contact.objects.filter(import_batch=batch).count()

        if remaining == 0:
            batch.delete()

        return Response({"deleted": len(ids), "total": total, "remaining": remaining})


class ContactViewSet(viewsets.ModelViewSet):
    serializer_class = ContactSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ["name", "email", "phone", "contact_id"]

    def get_serializer_class(self):
        if self.action == "list":
            return ContactListSerializer
        return ContactSerializer

    def get_queryset(self):
        qs = Contact.objects.all()
        qs = qs.select_related("import_batch")
        if self.action in ("retrieve", "update", "partial_update", "destroy"):
            qs = qs.prefetch_related(
                Prefetch(
                    "crm_pipelines",
                    queryset=CRM.objects.select_related("pipeline", "stage"),
                )
            )
        batch_id = self.request.query_params.get("batch")
        if batch_id:
            qs = qs.filter(import_batch_id=batch_id)
        assigned_user_id = self.request.query_params.get("assigned_user")
        if assigned_user_id:
            qs = qs.filter(crm_pipelines__assigned_user_id=assigned_user_id)
        return qs

    def perform_destroy(self, instance):
        batch = instance.import_batch
        instance.delete()
        # If the batch is now empty, delete it too
        if batch and not batch.contacts.exists():
            batch.delete()

    @action(detail=False, methods=["post"], url_path="bulk-create")
    def bulk_create(self, request):
        data = request.data
        if not isinstance(data, list):
            return Response(
                {"success": False, "message": "Expected a list of contacts"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        batch_name = request.query_params.get("batch_name") or "Unnamed Import"
        batch_id = request.query_params.get("batch_id")

        serializer = self.get_serializer(data=data, many=True)
        if not serializer.is_valid():
            return Response(
                {
                    "success": False,
                    "message": "Validation failed",
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get or Create the import batch
        if batch_id:
            try:
                batch = ImportBatch.objects.get(id=batch_id)
            except (ImportBatch.DoesNotExist, ValidationError):
                return Response(
                    {"success": False, "message": "Invalid batch_id provided"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            batch = ImportBatch.objects.create(name=batch_name)

        last_contact = Contact.objects.order_by("created_at").last()
        next_id_num = 1001
        if last_contact:
            try:
                # Get the numeric part of the last contact_id
                # Handles cases like CON-1001, CON-1002, etc.
                parts = last_contact.contact_id.split("-")
                if len(parts) > 1 and parts[1].isdigit():
                    next_id_num = int(parts[1]) + 1
            except (IndexError, ValueError):
                pass

        contact_objects = []
        for item_data in serializer.validated_data:
            contact = Contact(**item_data)
            contact.contact_id = f"CON-{next_id_num}"
            contact.import_batch = batch
            contact.source = batch.name
            if not item_data.get("status"):
                contact.status = "Imports"
            next_id_num += 1
            contact_objects.append(contact)

        try:
            Contact.objects.bulk_create(contact_objects)
            batch.contact_count += len(contact_objects)
            batch.save()

            # Bulk create import activity logs
            saved_contacts = Contact.objects.filter(import_batch=batch)
            log_objects = [
                ContactLog(
                    contact=c,
                    activity_type="Imported",
                    description=f"Contact imported from batch '{batch.name}'",
                    user=request.user,
                )
                for c in saved_contacts
            ]
            ContactLog.objects.bulk_create(log_objects, batch_size=1000)

            return Response(
                {
                    "success": True,
                    "message": f"Successfully imported {len(contact_objects)} contacts.",
                    "batch_id": str(batch.id),
                    "batch_name": batch.name,
                },
                status=status.HTTP_201_CREATED,
            )
        except Exception as e:
            # Only delete the batch if we just created it and it failed
            if not batch_id:
                batch.delete()
            return Response(
                {"success": False, "message": f"Database error: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ContactLogViewSet(viewsets.ModelViewSet):
    queryset = ContactLog.objects.all().select_related("contact", "crm", "user")
    serializer_class = ContactLogSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        contact_id = self.request.query_params.get("contact")
        crm_id = self.request.query_params.get("crm")

        if crm_id and contact_id:
            from django.db.models import Q

            qs = qs.filter(
                Q(crm_id=crm_id) | Q(contact_id=contact_id, crm_id__isnull=True)
            )
        elif contact_id:
            qs = qs.filter(contact_id=contact_id)
        elif crm_id:
            qs = qs.filter(crm_id=crm_id)

        return qs

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class ContactRemarkViewSet(viewsets.ModelViewSet):
    """Viewset for contact remarks/updates"""

    queryset = ContactRemark.objects.all()
    serializer_class = ContactRemarkSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        contact_id = self.request.query_params.get("contact")
        crm_id = self.request.query_params.get("crm")

        if crm_id and contact_id:
            from django.db.models import Q

            qs = qs.filter(
                Q(crm_id=crm_id) | Q(contact_id=contact_id, crm_id__isnull=True)
            )
        elif contact_id:
            qs = qs.filter(contact_id=contact_id)
        elif crm_id:
            qs = qs.filter(crm_id=crm_id)

        return qs

    def perform_create(self, serializer):
        remark = serializer.save(user=self.request.user)
        # Create an activity log for the remark
        ContactLog.objects.create(
            contact=remark.contact,
            crm=remark.crm,
            user=remark.user,
            activity_type="Remark Added",
            description=f'Added an update: "{remark.text}"',
        )


class ContactDocumentViewSet(viewsets.ModelViewSet):
    """Upload and manage files attached to contacts."""

    serializer_class = ContactDocumentSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ["file_name", "description"]

    def get_queryset(self):
        qs = ContactDocument.objects.select_related("contact", "uploaded_by")
        contact_id = self.request.query_params.get("contact")
        if contact_id:
            qs = qs.filter(contact_id=contact_id)
        return qs

    def perform_create(self, serializer):
        serializer.save(uploaded_by=self.request.user)
