# Calendar Architecture

## Overview

The calendar module manages 4 types of calendar entries: **Tasks**, **Events**, **Follow-ups**, and **Meetings**. All types share a single database model (`CalendarTodo`) with type-specific behavior driven by the `todo_type` field.

---

## Data Model (`CalendarTodo`)

### Fields

| Field | Type | Used By | Purpose |
|-------|------|---------|---------|
| `id` | UUID (PK) | All | Auto-generated unique ID |
| `user` | FK→User | All | Creator of the entry |
| `todo_type` | CharField(20) | All | `task`, `event`, `followup`, `meeting` |
| `title` | CharField(255) | All | Display title |
| `description` | TextField | All | Detailed notes |
| `priority` | CharField(10) | Task | `low`, `medium`, `high` |
| `start` | DateTimeField | All | Deadline (task), date/time (event/followup/meeting) |
| `end` | DateTimeField | Event | End of event range (optional) |
| `contact` | FK→Contact | Follow-up | Linked contact |
| `status` | CharField(20) | All | Type-specific status values |
| `hold_reason` | TextField | Task | Why task was put on hold |
| `extension_request` | TextField | Task | Text requesting deadline extension |
| `completion_remarks` | TextField | Task | Notes on completion |
| `location` | CharField(255) | Meeting | Venue or meeting link |
| `assigned_to` | FK→User | Task, Follow-up | Assignee |
| `created_at` | DateTime | All | Auto-set on creation |
| `updated_at` | DateTime | All | Auto-updated |

### MeetingAttendee (separate model)

Many-to-many relationship between meetings and users.

---

## Type-Specific Workflows

### 1. Task (`todo_type: "task"`)

**Statuses:** `assigned`, `progress`, `completed`, `canceled`, `on_hold`, `overdue`, `approved`

**Creation:**
- Required: Task Name, Deadline
- Optional: Description, Priority, Assign To
- Status defaults to auto-calculated by `save()` and `to_representation()`

**Auto-status (written on save + overridden on read):**
- If `start < now` and status NOT in `(completed, on_hold, approved, canceled)` → auto-set to `overdue`
- If `status == "overdue"` and `start > now` → auto-revert to `assigned`

**Status update cleanup (serializer `update`):**
- Leaving `on_hold` → `hold_reason` cleared
- Leaving `overdue` → `extension_request` cleared
- Leaving `completed` → `completion_remarks` cleared
- Changing `start` when `extension_request` exists → `extension_request` cleared

**UI (UpdateTaskModal):**
- Permission tiers:
  - `isAdmin && isCreator`: Full edit (title, description, priority, assigned_to, deadline)
  - `isCreator` (non-admin): Can edit deadline + status
  - Assignee (non-creator, non-admin): Can edit status only
  - Others: Read-only
- Mini PATCH flows: hold reason, extension request, completion remarks are sent as separate PATCH calls before the main form save

---

### 2. Event (`todo_type: "event"`)

**Statuses:** `upcoming`, `live`, `cancelled`, `ended`

**Creation (AddEventModal → Event tab):**
- Required: Event Name, Description, Event Date
- Optional: Status, Single Day toggle, End Date
- Save button disabled until title, start date, and description are filled

**Single Day toggle:**
- When ON: `end` is auto-set to `23:59:59` of the event date; End Date input is disabled
- When OFF: User can manually set an End Date for multi-day events
- Toggling ON resets start time to `00:00` (local time, no UTC conversion)
- Toggle is a switch component (not checkbox) placed inline with label

**Auto-status (written on save + overridden on read):**
- `cancelled` is never auto-overridden
- With `end` date:
  - `end < now` → `ended`
  - `start <= now <= end` and status is NOT manually `ended` → `live`
  - `start > now` → `upcoming`
- Without `end` date:
  - `start < now` and status is NOT manually `ended` → `ended`
  - else → `upcoming`
- Admin/creator manually setting status to `ended` is preserved (won't revert to `live`)

**Visibility:**
- ALL events are visible to ALL authenticated users in the calendar
- Backend query: `Q(todo_type="event")` is added to every user's base queryset

**Range overlap (multi-day events):**
- Events appear on ALL days between `start` and `end` (inclusive)
- Calendar grid dots: `eachDayOfInterval` in frontend
- EventsPanel/day queries: backend uses `Q(start__lt=end, end__isnull=False, end__gte=start)` for events
- This only applies to `todo_type="event"` — other types use start-only matching

**UI (UpdateEventModal):**
- Creator and Admin/Superadmin can edit all fields + delete
- Others: read-only (fields disabled, no banner message)
- Delete button: visible to both creator and admins
- Header: "Event Update" for editors, "Event" for read-only
- Status dropdown: `upcoming` and `cancelled` disabled when status is `live` or `ended`

---

### 3. Follow-up (`todo_type: "followup"`)

**Creation:**
- Required: Title, Contact, Follow-Up Date
- Optional: Notes, Assign To

**Behavior:**
- Minimal workflow — no status tracking, no auto-overdue
- Tied to a Contact record
- Can be assigned to a team member

---

### 4. Meeting (`todo_type: "meeting"`)

**Creation:**
- Required: Title, Date & Time
- Optional: Agenda, Location/Link, Attendees (multi-select from users)
- Attendees stored via `MeetingAttendee` model

**Behavior:**
- No status tracking
- Attendees are stored separately and returned in the API

---

## Backend Architecture

### Views (`CalendarTodoViewSet`)

- **Permissions:** `IsAuthenticated` (all endpoints require login)
- **Queryset filtering by user role:**
  - **Admin/Superadmin:** Own created todos `OR` all events
  - **Other roles:** Assigned to user, attendee of meeting, `OR` all events
- **Date filtering:**
  - When both `start` and `end` query params provided:
    - Events with range overlap are included (spanning multi-day events)
    - Other types: only items whose `start` falls within the range
- **Pagination:** CustomPageNumberPagination, page_size=100

### Serializers

- **`CalendarTodoSerializer`** handles all 4 types
- **Validation:**
  - Task: deadline required, valid task status values
  - Event: description required, date required, valid event status values, end must be after start
  - Follow-up: date required
  - Meeting: date required
  - End time must be after start time (all types)
- **Read-only fields:** `id`, `user`, `created_at`, `updated_at`
- **`to_representation`** overrides status at read time for tasks (overdue detection) and events (upcoming/live/ended detection)

### URLs

- `api/calendar/todos/` — list/create
- `api/calendar/todos/{id}/` — retrieve/update/delete
- Registered via DRF DefaultRouter

---

## Frontend Architecture

### Component Tree

```
CalendarPage (route)
└── CalendarComponent
    ├── EventsPanel (left sidebar)
    │   ├── AddEventModal (4 tabs: Tasks, Event, Follow-up, Meetings)
    │   ├── UpdateTaskModal
    │   ├── UpdateEventModal
    │   ├── UpdateFollowUpModal
    │   └── UpdateMeetingModal
    │   └── Card components: TaskCard, EventCard, FollowUpCard, MeetingCard
    └── Month grid (right side)
        ├── Day cells with colored dots
        └── Month navigation
```

### Data Flow

- **Month grid:** Fetches all todos for visible month → groups by date (`eventsByDate`) → shows colored dots per day
  - `eventsByDate` uses `eachDayOfInterval` for multi-day events
  - Dot colors: blue (task), emerald (event), amber (follow-up), purple (meeting)
- **EventsPanel:** Fetches all todos for the selected day independently (not from parent's cache)
- **Refresh:** Both components have `refreshTrigger`/`fetchKey` state that increments on event creation/update/deletion

### Key UX Patterns

- Modal portals rendered via `createPortal` to `document.body`
- Dropdown menus positioned using `getBoundingClientRect` + fixed positioning
- Color-coded status badges on cards and dropdown options
- Tabbed interface in AddEventModal (4 types in one modal)
- Mini PATCH flows for task-specific sub-actions (hold reason, completion remarks, extension requests)
