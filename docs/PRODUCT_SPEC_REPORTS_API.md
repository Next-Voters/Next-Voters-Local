# Product Spec: Reports API for nextvoters.com

## Overview

The NV Local pipeline now stores structured legislation reports in a Supabase `reports` database table instead of uploading HTML files to Supabase Storage. The website (`nextvoters.com`) must be updated to query this table using the Supabase JavaScript SDK and render the structured data client-side.

## Data Source

### `reports` table schema

| Column | Type | Description |
| --- | --- | --- |
| `report_id` | `bigint` (identity PK) | Auto-incrementing primary key. |
| `city` | `text` | City name. FK to `supported_cities(city)`. |
| `topic_id` | `integer` | Topic reference. FK to `supported_topics(topic_id)`. |
| `report_date` | `date` | Date the report covers. Defaults to `CURRENT_DATE`. |
| `items` | `jsonb` | Array of legislation items (see structure below). |
| `sources` | `text[]` | Array of source URLs cited in the report. |
| `created_at` | `timestamptz` | Row creation timestamp. |

**Unique constraint**: `(city, topic_id, report_date)` -- one report per city+topic per day. Pipeline re-runs upsert over the existing row.

### `items` JSONB structure

Each element in the `items` array is an object with two fields:

```json
[
  {
    "header": "Council passes good cause eviction package",
    "description": "The city council voted 8-3 to approve a package of tenant protections that requires landlords to provide a valid reason before evicting tenants. The bill applies to buildings with four or more units and takes effect January 1."
  },
  {
    "header": "Budget committee approves $2.1B infrastructure bond",
    "description": "The budget committee advanced a bond measure to fund road repairs, bridge maintenance, and public transit expansion. The full council is expected to vote next month, and if approved, it will appear on the November ballot."
  }
]
```

- `header`: Short factual headline (one line).
- `description`: 2-3 sentence plain-language explanation of what happened.

### Related lookup tables

**`supported_cities`**: `city text PK` -- list of active cities.

**`supported_topics`**: `topic_id integer PK`, `topic_name text UNIQUE`, `description text` -- current topics are `immigration`, `civil rights`, `economy`.

## Supabase JavaScript SDK Integration

### Setup

Install the Supabase JS client:

```bash
npm install @supabase/supabase-js
```

Initialize the client with the project's **anon (public) key** -- not the service role key:

```javascript
import { createClient } from '@supabase/supabase-js'

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
)
```

### RLS policy

The `reports` table currently has RLS enabled with a service-role-only policy. A read-only policy must be added for the anon key:

```sql
CREATE POLICY "Public read access to reports"
ON reports FOR SELECT
USING (true);
```

This allows any unauthenticated client to read reports. Write access remains restricted to the service role (pipeline backend).

## Query Patterns

### 1. Get today's reports for a city (all topics)

The primary landing page query -- fetches all topic reports for a city on the current date, with topic names resolved via join.

```javascript
const { data, error } = await supabase
  .from('reports')
  .select('report_id, city, topic_id, report_date, items, sources, supported_topics(topic_name)')
  .eq('city', city)
  .eq('report_date', new Date().toISOString().split('T')[0])
```

**Response shape**:

```json
[
  {
    "report_id": 42,
    "city": "San Francisco",
    "topic_id": 1,
    "report_date": "2026-05-05",
    "items": [{"header": "...", "description": "..."}],
    "sources": ["https://..."],
    "supported_topics": { "topic_name": "immigration" }
  }
]
```

### 2. Get the latest report for a specific city + topic

For topic-specific pages or deep links.

```javascript
const { data, error } = await supabase
  .from('reports')
  .select('report_id, report_date, items, sources, supported_topics(topic_name)')
  .eq('city', city)
  .eq('supported_topics.topic_name', topicName)
  .order('report_date', { ascending: false })
  .limit(1)
  .single()
```

### 3. Get report history for a city + topic

For an archive or historical view.

```javascript
const { data, error } = await supabase
  .from('reports')
  .select('report_id, report_date, items, sources')
  .eq('city', city)
  .eq('topic_id', topicId)
  .order('report_date', { ascending: false })
  .limit(30)
```

### 4. List all supported cities

```javascript
const { data, error } = await supabase
  .from('supported_cities')
  .select('city')
  .order('city')
```

### 5. List all supported topics

```javascript
const { data, error } = await supabase
  .from('supported_topics')
  .select('topic_id, topic_name, description')
  .order('topic_name')
```

## Frontend Rendering

### Rendering `items`

Each report's `items` array should be rendered as a list of cards or sections. Example React component:

```jsx
function ReportItems({ items }) {
  return (
    <div>
      {items.map((item, i) => (
        <article key={i}>
          <h3>{item.header}</h3>
          <p>{item.description}</p>
        </article>
      ))}
    </div>
  )
}
```

### Rendering `sources`

Sources are an array of URL strings. Render as a citation list at the bottom of each report section:

```jsx
function SourcesList({ sources }) {
  if (!sources?.length) return null
  return (
    <ul>
      {sources.map((url, i) => (
        <li key={i}>
          <a href={url} target="_blank" rel="noopener noreferrer">
            {new URL(url).hostname}
          </a>
        </li>
      ))}
    </ul>
  )
}
```

### Page structure

A city report page should:

1. Fetch all topics from `supported_topics`.
2. Fetch today's reports for the city (query pattern 1).
3. Group reports by topic and render each as a section with a heading (topic name), item cards, and source citations.
4. Show a fallback message for topics with no report for the current date.

## Environment Variables

The website needs two public Supabase credentials:

| Variable | Description |
| --- | --- |
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase project URL (e.g. `https://<project-ref>.supabase.co`) |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase anon/public API key (safe to expose client-side) |

These are the same credentials used across all Supabase JS SDK integrations. The anon key only grants access permitted by RLS policies.

## Migration Checklist

1. **Add public read RLS policy** on `reports` table (see RLS policy section above).
2. **Add public read RLS policy** on `supported_cities` and `supported_topics` if not already present.
3. **Install `@supabase/supabase-js`** in the website project.
4. **Set environment variables** (`NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`).
5. **Implement queries** using the patterns documented above.
6. **Remove any existing Supabase Storage fetch logic** (the storage bucket is no longer written to by the pipeline).
