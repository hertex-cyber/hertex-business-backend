# Deal Transforms — Architecture & Usage

## Overview

Deal Transforms is a 3-step wizard for selecting and moving deals into a new pipeline. It evolved from the original Lead Nurture feature, adding a **field-level filter** path alongside the traditional **stage-based** selection. Users can either pick deals by stage or filter by a specific `additional_data` key-value pair.

---

## Step Structure

| Step | Title | Purpose |
|------|-------|---------|
| 1 | Select Criteria | Choose **Stages** (multi-select) OR **Field Value** (single key-value) |
| 2 | Target Deals | Server-paginated deal list (50/page) with search and deselect |
| 3 | Create Pipeline | Name, description, department assignment, assignment strategy |

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

## Step 3 — Create Pipeline

- Name (required), description
- Department selection (for staff access control)
- Assignment strategy (round_robin, least_loaded, single_user, manual)

### Submission Flow

1. Create new pipeline via `POST /api/crm/pipelines/`
2. Fetch deals from source (with same filter path — stages or field value):
   - If stage selection: `stages=<ids>` 
   - If field value: `additional_field=X&additional_value=Y`
3. Send in chunks of 500 to `POST /api/crm/pipeline/bulk-add-contacts/` with `source_pipeline`
4. Backend **moves** deals (updates `pipeline_id`, `stage`, `priority="High"`, contact status → `"Retarget"`)
5. Progress bar shown for >100 selected deals

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

New query params for field filtering:
- `additional_field` — key name in contact's `additional_data`
- `additional_value` — exact value to match

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
| `LeadNurtureModal.jsx` | `crm/components/` | 3-step transform wizard (replaced Lead Nurture) |
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

## Known Limitations & Edge Cases

1. **Field value filter matches exact values** — `__contains` uses JSONB containment, which is exact for strings but not for partial matches
2. **Single-select only** — only one field + one value can be active at a time across the entire wizard
3. **No combined mode** — stages and field value cannot be used together; they are mutually exclusive paths
4. **System fields are not queryable** for value distribution — they're direct DB columns, not keys in `additional_data`
5. **Keys with special characters** — `additional_data` keys with spaces or special characters work via `->>` operator
