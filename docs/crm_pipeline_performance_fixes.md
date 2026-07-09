# CRM Pipeline Load Performance — Analysis & Fixes

## Symptom
CRM page and Lead Nurture modal were extremely slow to load even with small pipelines (e.g. 19 deals). The page would take several seconds to render.

## Root Causes Found

### 1. N+1 Query via Nested SerializerMethodField (ContactSerializer.get_pipelines)
**File:** `crm_backend/crm/serializers.py`

`CRMSerializer` imported and used the full `ContactSerializer` from the `contacts` app:

```python
from contacts.serializers import ContactSerializer

class CRMSerializer(serializers.ModelSerializer):
    contact_details = ContactSerializer(source='contact', read_only=True)
```

This `ContactSerializer` has a `SerializerMethodField` called `pipelines`:

```python
class ContactSerializer(serializers.ModelSerializer):
    pipelines = serializers.SerializerMethodField()

    def get_pipelines(self, obj):
        crm_deals = obj.crm_pipelines.all().select_related('pipeline', 'stage')
        # ... builds and returns a list
```

Even though the main CRM queryset used `select_related('contact')`, it did **not** prefetch the **reverse relation** `contact__crm_pipelines`. So `get_pipelines()` ran **1 extra query per deal** — 19 deals = 19 extra round trips to the database.

### 2. N+1 Query via Nested DepartmentSerializer (UserSerializer)
**File:** `crm_backend/crm/serializers.py` → `authentication/serializers.py`

`CRMSerializer` included `assigned_user_details = UserSerializer(source="assigned_user", read_only=True)`.

`UserSerializer` nests `departments = DepartmentSerializer(many=True, read_only=True)`.

`DepartmentSerializer` has `user_count = SerializerMethodField()` with `get_user_count` doing `obj.users.count()` — **1 extra COUNT query per department per user**.

Per deal row:
- 1 query to fetch the assigned user's M2M departments
- 1+ COUNT queries per department for `get_user_count`

For 19 deals with 3 unique assigned users, each having 2 departments: up to **3 × (1 + 2) = 9 extra queries** on top of the main query.

### 3. Bloated Payload — Pipeline Details Per Row
`pipeline_details = PipelineSerializer(source='pipeline')` serialized ALL stages (names, colors, orders) and ALL departments for every single deal row — even when all 19 deals belonged to the same pipeline. This multiplied the JSON payload size unnecessarily.

### 4. Silent Stage Filter Bug (UUID filter drop)
**File:** `crm_backend/crm/views.py`

```python
stage_ids = [s for s in stages.split(',') if s.isdigit()]
```

Stage IDs are UUIDs (e.g. `550e8400-e29b-41d4-a716-446655440000`). `isdigit()` returns `False` for UUIDs, so `stage_ids` was always empty. The stage filter was **silently dropped**, causing the API to return deals from ALL stages instead of just the selected ones.

---

## Fixes Applied

### Fix 1: Lightweight Contact Brief Serializer (N+1 Killer #1)
Created `ContactBriefSerializer` inside `crm/serializers.py`:

```python
class ContactBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contact
        fields = ["id", "name", "email", "phone", "status", "contact_id"]
```

Replaced `ContactSerializer` with `ContactBriefSerializer` in `CRMSerializer.contact_details`. Eliminates the `get_pipelines()` N+1 entirely.

### Fix 2: Lightweight User Brief Serializer (N+1 Killer #2)
Created `UserBriefSerializer` inside `crm/serializers.py`:

```python
class UserBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "mobile", "role", "is_active"]
```

Replaced `UserSerializer` with `UserBriefSerializer` in `CRMSerializer.assigned_user_details`. Eliminates the nested `DepartmentSerializer` + `get_user_count()` N+1.

### Fix 3: Remove Pipeline Details From Deal Rows
Removed `pipeline_details = PipelineSerializer(source="pipeline")` from `CRMSerializer`. The pipeline FK ID (`pipeline` field) remains for reference.

### Fix 4: UUID Stage Filter Fix
```python
# Before (broken):
stage_ids = [s for s in stages.split(",") if s.isdigit()]

# After (fixed):
stage_ids = [s for s in stages.split(",") if s]
```

### Fix 5: Prefetch Safety Net
Updated the CRMViewSet queryset prefetch:

```python
# Before:
.prefetch_related("contact__crm_pipelines__pipeline", "contact__crm_pipelines__stage")

# After (no longer needed since brief serializers don't trigger reverse relations):
# Removed entirely
```

---

## Current State of crm/serializers.py (Post-Fix)

```python
from rest_framework import serializers
from crm.models import CRM, Pipeline, Stage
from contacts.models import Contact
from authentication.models import User, Department
from authentication.serializers import DepartmentSerializer


class UserBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "mobile", "role", "is_active"]


class StageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Stage
        fields = ["id", "pipeline", "name", "slug", "order", "color"]
        read_only_fields = ["id", "slug", "pipeline"]


class PipelineSerializer(serializers.ModelSerializer):
    stages = StageSerializer(many=True, read_only=True)
    departments = DepartmentSerializer(many=True, read_only=True)
    department_ids = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(),
        source="departments",
        many=True,
        required=False,
        write_only=True,
    )

    class Meta:
        model = Pipeline
        fields = [
            "id", "name", "description", "stages", "departments",
            "department_ids", "assignment_type", "mandatory_fields",
            "custom_fields_enabled", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class ContactBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contact
        fields = ["id", "name", "email", "phone", "status", "contact_id"]


class CRMSerializer(serializers.ModelSerializer):
    contact_details = ContactBriefSerializer(source="contact", read_only=True)
    stage_details = StageSerializer(source="stage", read_only=True)
    assigned_user_details = UserBriefSerializer(source="assigned_user", read_only=True)

    class Meta:
        model = CRM
        fields = [
            "id", "contact", "contact_details",
            "pipeline",
            "stage", "stage_details",
            "assigned_user", "assigned_user_details",
            "value", "priority", "notes",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
```

## Current State of crm/views.py (Post-Fix)

```python
class CRMViewSet(viewsets.ModelViewSet):
    queryset = (
        CRM.objects.all()
        .select_related("contact", "pipeline", "stage", "assigned_user")
    )
    serializer_class = CRMSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset()
        if user.is_authenticated and user.role == "Staff":
            qs = qs.filter(assigned_user=user)

        stage_id = self.request.query_params.get("stage")
        stages = self.request.query_params.get("stages")
        pipeline_id = self.request.query_params.get("pipeline")
        search = self.request.query_params.get("search")

        if stage_id:
            qs = qs.filter(stage_id=stage_id)
        if stages:
            stage_ids = [s for s in stages.split(",") if s]
            if stage_ids:
                qs = qs.filter(stage_id__in=stage_ids)
        if pipeline_id:
            qs = qs.filter(pipeline_id=pipeline_id)
        if search:
            from django.db.models import Q
            search_by = self.request.query_params.get("search_by", "name")
            allowed = {"name", "email", "phone"}
            fields = [f.strip() for f in search_by.split(",") if f.strip() in allowed]
            if not fields:
                fields = ["name"]
            q = Q()
            if "name" in fields:
                q |= Q(contact__name__icontains=search)
            if "email" in fields:
                q |= Q(contact__email__icontains=search)
            if "phone" in fields:
                q |= Q(contact__phone__icontains=search)
            qs = qs.filter(q)
        return qs
```

---

## Remaining Notes

- **Pagination**: Global `PageNumberPagination` with `PAGE_SIZE=100`. Lead Nurture modal overrides with `page_size: 1000`.
- **PipelineSerializer** still uses `DepartmentSerializer` with `get_user_count()` — this only fires for `GET /api/crm/pipelines/` (list view), not per deal, so it's fine.
- **No database indexes** on `Contact.name`, `Contact.email`, `Contact.phone` — `icontains` text searches remain slow at scale.
- **UUID primary keys** on all CRM/Contact models — index fragmentation may impact performance at very high volumes (>100k rows).
- **No polling/refetching** in the CRM frontend page.
- **No django-filter** — all filtering is manual via `get_queryset()`.