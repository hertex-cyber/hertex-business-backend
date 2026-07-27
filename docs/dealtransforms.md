# Deal Transforms — Architecture & Usage

## Overview

Deal Transforms is a 4-step wizard for selecting and moving deals into a new pipeline. It evolved from the original Lead Nurture feature, adding a **field-level filter** path alongside the traditional **stage-based** selection. Users can either pick deals by stage or filter by a specific `additional_data` key-value pair.

---

## Step Structure

| Step | Title | Purpose |
|------|-------|---------|
| 1 | Select Criteria | Choose **Stages** (multi-select) OR **Field Value** (single key-value) |
| 2 | Target Deals | Server-paginated deal list (50/page) with search and deselect |
| 3 | Choose Action | Select **Retargeting**, **Add to Pipeline**, or **Move to Pipeline** |
| 4 | Pipeline Setup | Name, description, department assignment, assignment strategy |

---

## Step 1 — Select Criteria

Two mutually exclusive tabs sit in the subheader pill toggle:

### Tab A: Select Stages (multi-select)

- Grid of stage cards, 2 per row, matching the pipeline's stages
- Click toggles selection (multi-select)
- Each card shows a check indicator when selected
- Gradient overlay on hover/selected (`bg-blue-500/10` + `from-blue-500/0 via-blue-500/0 to-blue-500/5`)
- "Next" requires at least one stage selected

### Tab B: Select Fields (single key-value)

Lists all fields from `pipeline.mandatory_fields`:

**System Fields** (`Name`, `Email`, `Phone`):
- Rendered as muted, non-interactive cards with `opacity-40` and a "System" badge
- Not queryable — they're direct DB columns, not in `additional_data`
- No expand, no chevron, no selection

**Custom/Additional Fields**:
- Rendered as expandable cards with a chevron and selection count badge
- Clicking a field card expands its value distribution dropdown
- Each value row shows:
  - Radio circle indicator (single-select — `rounded-full border-2`, dot when active)
  - Value name
  - Occurrence count
- Only **one** value can be selected across **all** fields
- Clicking the same value again deselects it
- "Next" requires a field value selected
- Expanded dropdown caps at 7 rows (`max-h-[280px]`) with scroll

#### State
```javascript
const [selectedFilter, setSelectedFilter] = useState(null);
// Shape: { field: "Payment Status", value: "Paid" }
const [expandedField, setExpandedField] = useState(null);
const [fieldValues, setFieldValues] = useState({});
// Shape: { "Payment Status": { field, total: 165, values: [{ value: "Paid", count: 120 }, ...] } }
const [loadingValues, setLoadingValues] = useState(null);
```

---

### LeadSettingsModal — Configuring Fields

The `LeadSettingsModal.jsx` manages which fields appear in the Select Fields tab via `pipeline.mandatory_fields`:

- **System fields** (`Name`, `Email`, `Phone`) — always present, non-removable
- **Custom fields** — user-defined, added manually or via **Track Fields**
- **Toggle**: `custom_fields_enabled` — when off, custom fields are disabled in the modal and the Select Fields tab gets a tooltip ("Custom field not enabled")

#### Track Fields Button

- Positioned inline with "Configured Fields" label (right-aligned)
- Calls `GET /api/contacts/track-fields/?pipeline_id=X`
- Deduplicates against system fields + existing custom fields
- Appends tracked field names as new custom field pills

**Backend** — `ContactViewSet.track_fields`:
```sql
SELECT DISTINCT jsonb_object_keys(c.additional_data)
FROM contacts_contact c
JOIN crm_crm deal ON deal.contact_id = c.id
WHERE deal.pipeline_id = %s
  AND c.additional_data IS NOT NULL
  AND c.additional_data != '{}'::jsonb
```

Filters out system field names (`name`, `email`, `phone`, `status`, `contact_id`, `source`, `id`, `created_at`, `updated_at`).

---

## Step 1 → Step 2 — Data Flow

### When using Stage Selection
`fetchDeals` sends:
```
GET /api/crm/pipeline/?pipeline=<id>&stages=<id1,id2>&page=1&page_size=50
```
Backend filters by `pipeline_id` AND `stage_id__in`.

### When using Field Value Selection
`fetchDeals` sends:
```
GET /api/crm/pipeline/?pipeline=<id>&additional_field=Payment%20Status&additional_value=Paid&page=1&page_size=50
```
Backend filters by `pipeline_id` AND `contact__additional_data__contains={field: value}`.

**Backend** — `CRMViewSet.get_queryset`:
```python
additional_field = self.request.query_params.get("additional_field")
additional_value = self.request.query_params.get("additional_value")

if additional_field and additional_value:
    qs = qs.filter(
        contact__additional_data__contains={additional_field: additional_value}
    )
```

The two filtering modes are independent — only one set of params is sent based on `activeTab`.

---

## Step 2 — Target Deals

- Server-paginated list (50 per page)
- All fetched deals are implicitly selected
- Users manually uncheck deals → tracked in `deselectedDealIds` (a `Set`)
- Top badge shows `Total leads: totalDealCount - deselectedDealIds.size`
- `totalDealCount` comes from `response.data.count`
- Search with 300ms debounce, filterable by name/email/phone
- "Load More" fetches next page, appends to display

---

## Step 3 — Choose Action

Three mutually exclusive action cards with radio indicators:

| Action | Description | Backend Endpoint | Behavior |
|--------|-------------|-----------------|----------|
| **Retargeting** (default) | Move deals into retarget pipeline, High priority, contact status → "Retarget" | `bulk-add-contacts` with `source_pipeline`, `priority: "High"` | Updates `pipeline_id` on existing CRM rows, resets `assigned_user`, sets priority=High, sets contact status=Retarget |
| **Add to Pipeline** | Copy contacts into pipeline without altering existing deals. Creates new CRM entries | `bulk-add-to-pipeline` with `deal_ids` | Creates fresh CRM entries, preserves contact info, no status change |
| **Move to Pipeline** | Move the deal to a new pipeline. Same CRM ID preserved, `assigned_user` reset. No status/priority change | `bulk-add-contacts` with `source_pipeline`, `priority` (preserved), `skip_contact_status_update: true` | Updates `pipeline_id` on existing CRM rows, preserves priority, no contact status change |

---

## Step 4 — Pipeline Setup

### Pipeline Resolution

- **Retargeting**: Can select an **existing** retarget pipeline from the list (fetched via `GET /api/crm/pipelines/?pipeline_type=retarget`) OR click "+ New" to create one with `pipeline_type='retarget'`
- **Add/Move**: Always creates a new pipeline (name input + description)

### Retarget Pipeline List

- Wrapped in a `rounded-lg border border-zinc-800 bg-zinc-900/20` container
- Pipelines rendered in a `grid grid-cols-2 gap-2` (2 per row)
- Count shown inline in the label: `Available Retarget Pipelines: 10`
- "+ New" button sits outside the container, to the right of the label
- List has its own scroll (`max-h-44 overflow-y-auto pr-2`) inside the container
- Selecting a pipeline populates name/description and hides the create form

### Assignment

- Department group selection (toggle shows searchable dropdown)
- Assignment strategies: Single User, Round Robin, Manual (no auto-assign)
- After moving deals, calls `POST /api/crm/pipelines/{id}/trigger-assignment/` if strategy is not manual

### Submission Flow

1. **Resolve target pipeline**: existing ID (retarget) or create new via `POST /api/crm/pipelines/`
2. **Fetch deals** from source (paged at 500, same filter path — stages or field value)
3. **Send action-specific API call** in chunks of 500:
   - Retarget: `bulk-add-contacts` with `source_pipeline`
   - Add: `bulk-add-to-pipeline` with `deal_ids`
   - Move: `bulk-add-contacts` with `source_pipeline` + `skip_contact_status_update: true`
4. **Auto-assign** if strategy is not manual (calls `trigger-assignment`)
5. Progress bar shown during processing

---

## API Endpoints

### Backend — Contact Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/contacts/track-fields/` | Return unique `additional_data` keys from contacts in a pipeline |
| GET | `/api/contacts/track-field-values/` | Return value distribution for a specific field key |

**`track-field-values` params**: `field` (required), `pipeline_id` (optional)

Query:
```sql
SELECT c.additional_data->>%s AS val, COUNT(*) AS cnt
FROM contacts_contact c
JOIN crm_crm deal ON deal.contact_id = c.id
WHERE deal.pipeline_id = %s
  AND c.additional_data ? %s
GROUP BY val ORDER BY cnt DESC
```

Response:
```json
{
  "field": "Payment Status",
  "total": 165,
  "values": [
    { "value": "Paid", "count": 120 },
    { "value": "Not Paid", "count": 45 }
  ]
}
```

### Backend — CRM Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/crm/pipeline/` | List deals, filterable by pipeline/stages/additional_field |
| POST | `/api/crm/pipeline/bulk-add-contacts/` | Move deals to pipeline. Optional: `priority` (default "High"), `skip_contact_status_update` (default false) |
| POST | `/api/crm/pipeline/bulk-add-to-pipeline/` | Copy deals to pipeline (new CRM entries) |

New query params for field filtering:
- `additional_field` — key name in contact's `additional_data`
- `additional_value` — exact value to match

---

## Step 4 — Pipeline Type on Create

When creating a new pipeline from the wizard, the `pipeline_type` is set based on the action:
- `retarget` for Retargeting action (so the pipeline appears in retarget pipeline lists)
- Not set (null/default) for Add/Move actions

---

## Key Differences: Stage Selection vs Field Selection

| Aspect | Stages Tab | Fields Tab |
|--------|-----------|------------|
| **Selection type** | Multi-select cards | Single-select (one field, one value) |
| **Data source** | Pipeline stages | `mandatory_fields` from pipeline config |
| **System fields** | N/A | Disabled (Name, Email, Phone) |
| **Filter backend** | `stage_id__in` | `contact__additional_data__contains` |
| **API param** | `stages=<ids>` | `additional_field=X&additional_value=Y` |
| **Validation** | "Select at least one stage" | "Select a field value pair" |

---

## Related Components

| Component | Path | Purpose |
|-----------|------|---------|
| `LeadNurtureModal.jsx` | `crm/components/` | 4-step transform wizard (replaced Lead Nurture) |
| `LeadSettingsModal.jsx` | `crm/components/` | Configure mandatory fields + Track Fields |
| `AddToCRMModal.jsx` | `contacts/components/` | Add contacts from imports to CRM pipeline |
| `Tooltip` | `components/ui/tooltip.jsx` | Tooltip for disabled state (custom fields not enabled) |

---

## Serializer Changes

### ContactBriefSerializer (`crm/serializers.py`)
Added `additional_data` and `source` to expose contact's unstructured data in CRM deal responses:
```python
class ContactBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contact
        fields = ["id", "name", "email", "phone", "status", "contact_id", "additional_data", "source"]
```

### ContactListSerializer (`contacts/serializers.py`)
Added `additional_data` to ensure the contacts list API returns it:
```python
fields = ["id", "name", "email", "phone", "status", "contact_id", "source", "additional_data", "created_at"]
```

---

## Action Comparison

| Aspect | Retarget | Add | Move |
|--------|----------|-----|------|
| **Operation** | MOVE (update pipeline_id) | COPY (new CRM entries) | MOVE (update pipeline_id) |
| **Priority** | Set to "High" | Set to "Medium" | Preserved from source |
| **Contact Status** | Changed to "Retarget" | Unchanged | Unchanged |
| **Deal IDs** | Same IDs preserved | New IDs created | Same IDs preserved |
| **Use Case** | Retargeting campaign | Cross-pipeline listing | Pipeline reorganization |

---

## Known Limitations & Edge Cases

1. **Field value filter matches exact values** — `__contains` uses JSONB containment, which is exact for strings but not for partial matches
2. **Single-select only** — only one field + one value can be active at a time across the entire wizard
3. **No combined mode** — stages and field value cannot be used together; they are mutually exclusive paths
4. **System fields are not queryable** for value distribution — they're direct DB columns, not keys in `additional_data`
5. **Keys with special characters** — `additional_data` keys with spaces or special characters work via `->>` operator
6. **Contact dedup on move** — If a contact has multiple deals in the source pipeline, all move together since the API filters by `contact_id__in`. The UI shows individual deals, but the backend moves by contact.
