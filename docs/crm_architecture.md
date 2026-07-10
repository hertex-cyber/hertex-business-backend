# CRM Architecture

## Overview

The CRM module manages sales pipelines with dynamic stages, drag-and-drop Kanban board, deal tracking, and a Lead Nurture feature that creates retarget pipelines. Built with Django REST Framework (3.17.1) backend and React frontend.

---

## Database Models

### Pipeline (`crm/models.py`)
- `name`, `description` — basic info
- `departments` — M2M to `authentication.Department` (staff access control)
- `assignment_type` — `round_robin`, `least_loaded`, or `manual`
- `mandatory_fields` — JSON list of required fields per pipeline
- `custom_fields_enabled` — toggle for custom fields
- Auto-creates 6 default stages on creation: Lead, Qualified, Proposal, Negotiation, Won, Lost

### Stage (`crm/models.py`)
- FK to `Pipeline`
- `name`, `slug`, `order`, `color` (`blue`, `purple`, `amber`, `orange`, `green`, `red`, `pink`, `cyan`)
- `unique_together = ('pipeline', 'slug')`

### CRM (`crm/models.py`) — the "deal" table
- FK to `Pipeline` (nullable)
- FK to `Stage` (nullable, SET_NULL on delete)
- FK to `Contact` (CASCADE)
- FK to `assigned_user` (nullable, SET_NULL)
- `value` — DecimalField
- `priority` — `Low` / `Medium` (default) / `High`
- `notes` — TextField
- DB indexes: `(pipeline, stage)`, `(created_at)`, `(pipeline, assigned_user)`

### Priority Choices
| Value | Display |
|-------|---------|
| Low   | Low     |
| Medium| Medium  |
| High  | High    |

### Stage Color Choices
`blue`, `purple`, `amber`, `orange`, `green`, `red`, `pink`, `cyan`

### Contact Status (from contacts app)
Standard: `Lead`, `Prospect`, `Customer`, `Inactive`, **`Retarget`** (added for Lead Nurture)

---

## Backend Architecture

### Settings (`core/settings.py`)
```python
REST_FRAMEWORK = {
    "DEFAULT_PAGINATION_CLASS": "core.pagination.CustomPageNumberPagination",
    "PAGE_SIZE": 100,
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        ...
    ],
}
```

**Note:** DRF 3.17.1's `PageNumberPagination` does NOT read `PAGE_SIZE_QUERY_PARAM` or `MAX_PAGE_SIZE` from settings. A custom class is required.

### Custom Pagination (`core/pagination.py`)
```python
class CustomPageNumberPagination(PageNumberPagination):
    page_size_query_param = "page_size"
    max_page_size = 1000
```

### Serializers (`crm/serializers.py`)

| Serializer | Purpose | Fields |
|------------|---------|--------|
| `UserBriefSerializer` | Lightweight user (avoids N+1 from DepartmentSerializer) | id, email, first_name, last_name, mobile, role, is_active |
| `ContactBriefSerializer` | Lightweight contact (avoids N+1 from ContactSerializer.get_pipelines) | id, name, email, phone, status, contact_id |
| `StageSerializer` | Stage CRUD | id, pipeline, name, slug, order, color |
| `PipelineSerializer` | Pipeline with nested stages + departments | Full pipeline with embedded stages + departments |
| `CRMSerializer` | Deal CRUD with nested brief serializers | contact_details (ContactBrief), stage_details (StageSerializer), assigned_user_details (UserBriefSerializer) |

### Views (`crm/views.py`)

#### CRMViewSet
- `queryset`: `CRM.objects.all().select_related("contact", "pipeline", "stage", "assigned_user")`
- Filtering: stage, stages (comma-separated), pipeline, search (by name/email/phone)
- **Stage filter fix**: UUID stage IDs were silently dropped by `s.isdigit()` — changed to `if s`
- Pagination: respects `page_size` query param via `CustomPageNumberPagination`
- `perform_create`: auto-assignment via round_robin or least_loaded algorithms
- `create_deal`: custom endpoint for creating single deals with contact lookup
- `bulk_add_contacts`: moves deals from source pipeline to new pipeline with:
  - `priority="High"` set on moved deals (retarget deals get high priority)
  - Contact status updated to `"Retarget"`
  - Activity log entries (`ContactLog`) created per deal
  - Chunked processing supported (frontend sends in groups of 100)

#### PipelineViewSet
- `queryset`: `Pipeline.objects.prefetch_related("stages", "departments")`
- Staff filtering: restricts to pipelines whose departments match user's departments
- `perform_create`: auto-creates default stages (Lead → Lost)
- `assignment_stats`: endpoint returning deal counts and user loads

---

## Frontend Architecture

### Component Tree

```
CRM.jsx (page)
├── PipelineSelector
├── KanbanColumn (KanbanBoard.jsx)
│   └── KanbanCard (KanbanCard.jsx)
├── CreatePipelineModal
├── SearchDialog
├── DealDetailsDialog
├── AddLeadDialog / AddLeadStructured
├── ConfirmDeleteDialog
├── Actions
└── LeadNurtureModal
```

### CRM.jsx — Main Kanban Page
- **State**: `deals` — keyed by stage ID, each entry has `{ items, nextPage, hasMore, count, isLoadingMore }`
- **Fetching**: `fetchDeals()` — parallel requests per stage, 100 deals per page, server-side paginated
- **Load More**: `fetchMoreDeals(stageId)` — fetches next page for a specific stage, appends to existing items
- **Drag & Drop**: `@dnd-kit` with `PointerSensor`, drag overlay renders `KanbanCardUI`
- **Pipeline Selection**: stored in `localStorage('crm_selected_pipeline_id')`
- **Tabs**: `pipeline` (Kanban view) / `actions` (admin tools)

### KanbanBoard.jsx — KanbanColumn
- `useDroppable` from `@dnd-kit` for each column
- `SortableContext` with `verticalListSortingStrategy`
- Column color derived from stage color via `getColumnColor()`
- Shows `Load More (X/Y)` button when `hasMore` is true

### KanbanCard.jsx — Deal Card
- `useSortable` from `@dnd-kit` for drag
- `KanbanCardUI` — presentational component (also used in drag overlay)
- **Status colors** (contact status badges):
  | Status   | Style |
  |----------|-------|
  | Lead     | blue gradient |
  | Prospect | purple gradient |
  | Customer | green gradient |
  | Inactive | zinc gradient |
  | Retarget | **amber gradient** |
- **Priority colors** (priority badges):
  | Priority | Style |
  |----------|-------|
  | High     | red background/border |
  | Medium   | amber background/border |
  | Low      | emerald background/border |

### LeadNurtureModal.jsx — Lead Nurture Setup

A 3-step wizard modal for creating retarget pipelines:

**Step 1: Select Stages** — User picks source stages from the current pipeline.

**Step 2: Target Deals** — Server-side paginated deal list (50 per page).
- All deals from selected stages are implicitly selected.
- User manually unchecks deals → tracked in `deselectedDealIds` (Set).
- Top badge shows `Total leads: totalDealCount - deselectedDealIds.size`
- `totalDealCount` comes from `response.data.count` — static total unaffected by pagination.
- Search with 300ms debounce, filterable by name/email/phone.
- "Load More" fetches next page from server, appends to display.

**Step 3: Create Pipeline** — Name, description, optional department assignment.

**Submission Flow** (triggered by "Create & Retarget"):
1. Create new pipeline via `POST /api/crm/pipelines/`
2. **If total selected > 100**: fetch all remaining pages from server
3. **If total selected > 100**: show progress bar (replaces right-side stepper indicators)
   - Phase 1: "Collecting deals..." (during remaining page fetches)
   - Phase 2: "Moving deals to retarget pipeline..." (during chunked submission)
4. Send deals in **chunks of 100** to `POST /api/crm/pipeline/bulk-add-contacts/` with `source_pipeline` param
5. Backend **moves** deals (updates `pipeline_id`, `stage`, `priority="High"`) and updates contact status to `"Retarget"`
6. Footer shows "Processing, please wait..." during submission
7. Calls `onPipelineCreated(newPipeline)` on success

**Progress Bar**: Only replaces the right-side stepper indicators (3 numbered circles), not the left-side title/description/total leads. Uses `w-48` fixed width with phase label, progress bar, and count.

---

## API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/crm/pipeline/` | List deals (paginated, filterable) |
| POST | `/api/crm/pipeline/` | Create deal |
| PATCH | `/api/crm/pipeline/{id}/` | Update deal |
| DELETE | `/api/crm/pipeline/{id}/` | Delete deal |
| POST | `/api/crm/pipeline/create_deal/` | Create deal with contact lookup |
| POST | `/api/crm/pipeline/bulk-add-contacts/` | Move deals to retarget pipeline |
| GET | `/api/crm/pipelines/` | List pipelines |
| POST | `/api/crm/pipelines/` | Create pipeline |
| GET | `/api/crm/pipelines/{id}/` | Pipeline detail |
| PATCH | `/api/crm/pipelines/{id}/` | Update pipeline |
| DELETE | `/api/crm/pipelines/{id}/` | Delete pipeline |
| GET | `/api/crm/pipelines/{id}/assignment-stats/` | Assignment breakdown |
| GET | `/api/crm/stages/` | List stages |
| POST | `/api/crm/stages/` | Create stage |
| PATCH | `/api/crm/stages/{id}/` | Update stage |
| DELETE | `/api/crm/stages/{id}/` | Delete stage |

---

## Performance Fixes

### 1. N+1 Query — ContactSerializer.get_pipelines (Fixed)
`CRMSerializer` used `ContactSerializer` which has a `SerializerMethodField('pipelines')`. This fired 1 extra query per deal on the reverse `crm_pipelines` relation. **Fixed** by replacing with `ContactBriefSerializer` that only exposes flat fields.

### 2. N+1 Query — UserSerializer → DepartmentSerializer → get_user_count (Fixed)
`UserSerializer` nested `DepartmentSerializer` which has a `SerializerMethodField('user_count')`. For each deal's assigned user, this queried all departments + COUNT queries. **Fixed** by replacing with `UserBriefSerializer`.

### 3. Bloated Payload — Pipeline Details Per Row (Fixed)
Removed `PipelineSerializer` from each deal row. The pipeline FK ID remains, but stages/departments are no longer serialized per deal.

### 4. Stage UUID Filter Bug (Fixed)
`stage_ids = [s for s in stages.split(',') if s.isdigit()]` silently dropped UUID stage IDs. Changed to `if s`.

### 5. Prefetch Cleanup
Removed unnecessary `.prefetch_related("contact__crm_pipelines__pipeline", ...)` since brief serializers don't trigger reverse relations.

---

## Known Limitations

- **No database indexes** on `Contact.name`, `Contact.email`, `Contact.phone` — `icontains` text searches are slow at scale
- **UUID primary keys** may cause index fragmentation at >100k rows
- **No polling/SSE/WebSocket** — the CRM page does not auto-refresh
- **No django-filter** — all filtering is manual in `get_queryset()`
- `PipelineSerializer` still uses `DepartmentSerializer` with `get_user_count()` — acceptable since it only fires on `GET /pipelines/` (list), not per deal

---

## Frontend File Reference

| File | Role |
|------|------|
| `crm_frontend/src/modules/crm/pages/CRM.jsx` | Main Kanban page |
| `crm_frontend/src/modules/crm/components/KanbanBoard.jsx` | KanbanColumn droppable component |
| `crm_frontend/src/modules/crm/components/KanbanCard.jsx` | Draggable deal card with status/priority colors |
| `crm_frontend/src/modules/crm/components/LeadNurtureModal.jsx` | 3-step retarget wizard modal |
| `crm_frontend/src/modules/crm/components/CreatePipelineModal.jsx` | Pipeline creation modal |
| `crm_frontend/src/modules/crm/components/DealDetailsDialog.jsx` | Deal detail view |
| `crm_frontend/src/modules/crm/components/AddLeadDialog.jsx` | Quick lead add |
| `crm_frontend/src/modules/crm/components/AddLeadStructured.jsx` | Structured lead add with fields |
| `crm_frontend/src/modules/crm/components/PipelineSelector.jsx` | Pipeline dropdown |
| `crm_frontend/src/modules/crm/components/Actions.jsx` | Admin actions panel |

## Backend File Reference

| File | Role |
|------|------|
| `crm_backend/crm/models.py` | Pipeline, Stage, CRM models |
| `crm_backend/crm/views.py` | CRMViewSet, PipelineViewSet |
| `crm_backend/crm/serializers.py` | All CRM serializers |
| `crm_backend/core/pagination.py` | CustomPageNumberPagination |
| `crm_backend/core/settings.py` | Django + DRF config |
