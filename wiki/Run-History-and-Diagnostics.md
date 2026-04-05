# Run History and Diagnostics

> **Workflow:** [[Creating a Connector|Connector]] > [[Endpoints and Field Discovery|Endpoints]] > [[Canvases and Endpoint Chaining|Canvas]] > [[Field Mapping|Mapping]] > [[Scheduling|Schedule]] > **Run History**

After scheduling a connector, use Run History to monitor sync results and diagnose failures. This page covers how to read run results, understand enrichment levels, and use the fault diagnosis tools.

## How Enrichment Works

When a canvas has child endpoints that enrich the base endpoint's records, each record is classified by how much enrichment it received during the sync.

- **Full enrichment** -- The base record was enriched by all child endpoints in the canvas tree. Every child endpoint returned data for this record.
- **Partial enrichment** -- The base record was enriched by some but not all child endpoints. At least one child endpoint returned data, but others did not (possibly due to no matching records or errors).
- **Base only** -- The base record had no successful child enrichment. It was submitted to Qualys with only the data from the root endpoint.

If a connector has no child endpoints (single-endpoint canvas), all records are reported as full enrichment.

The run detail page displays enrichment counts so you can see at a glance how many records received full, partial, or base_only enrichment.

## Run History Page

The **Run History** page (accessible from the sidebar) shows all sync runs across all connectors with:

- **Status** badge (success, partial_success, failed, running)
- **Connector name**
- **Start/finish timestamps**
- **Records fetched / submitted / failed** counts
- **Triggered by** (manual or schedule)

### Filtering

Use the filter controls at the top of the run list to narrow results:

- **Connector filter** -- A dropdown listing all connectors. Select a connector to show only its runs.
- **Status filter** -- A dropdown with success, partial_success, failed, and running options. Select a status to show only matching runs.
- **Date range** -- From and to date pickers that filter by run start time.

All filters are server-side (not client-side) and combine with AND logic. For example, selecting a connector and a status shows only runs for that connector with that status. Results are paginated with server-side pagination, so filters apply to the full dataset, not just the current page.

## Run Detail Page

Click on any run to see full details.

### Summary Section

- Overall status, timing, and record counts
- Enrichment breakdown: full, partial, and base_only record counts
- Error type and message (if failed)

### Endpoint Logs

Each endpoint that participated in the run has its own log entry showing:

| Field | Description |
|-------|-------------|
| **Endpoint Name** | Name of the connector endpoint |
| **Endpoint Path** | API path that was called |
| **Canvas Name** | Which canvas this endpoint belongs to |
| **Execution Order** | Order in which this endpoint was processed |
| **Status** | Per-endpoint status (success, failed, partial_success) |
| **Records Fetched** | Number of records retrieved from the source API |
| **Records Submitted** | Number of records successfully submitted to Qualys |
| **Records Failed** | Number of records that failed Qualys submission |
| **Records Filtered** | Number of records excluded by exclusion rules |
| **Failure Stage** | Where the failure occurred: `source_fetch`, `transformation`, or `qualys_submit` |
| **Error Message** | Detailed error message |

### Child Request Statistics

For chained endpoints, additional statistics show:

- **Child Requests Total** -- how many child API calls were made
- **Child Requests Failed** -- how many child calls failed
- **Child Requests Skipped** -- how many were skipped (e.g., template resolution failure)
- **Depth** -- the chain depth level

### Failure Details

If individual records failed Qualys submission, the **Failures** section shows:

- **Record Identifier** -- which record failed
- **Error Message** -- the Qualys error for that record

## Fault Diagnosis

When a sync fails or produces unexpected results, fault diagnosis captures the full HTTP request and response for each endpoint call. This is off by default to limit storage usage.

1. Open the connector's settings page.
2. Enable the **Fault Diagnosis** toggle (off by default).
3. Trigger a sync (manually or wait for a scheduled run).
4. Open the run detail page. Each endpoint log now includes additional diagnostic data:
   - **HTTP Request**: method, URL, headers (credentials redacted based on auth type -- the Authorization header for bearer/basic auth, or the custom header name for api_key auth)
   - **HTTP Response**: status code, headers, response body (truncated to 16 KB)
   - **Detail Events**: API calls, transform decisions, exclusion rule results
5. Use the **copy-to-clipboard** button on request/response captures to share diagnostic data with support or for offline analysis.

> **Note:** Fault diagnosis increases database storage. Disable the toggle after debugging is complete.

## Payload Retention

Captured HTTP payloads and detail events are automatically purged after **14 days**. The cleanup process:

- Nulls out the `http_request` and `http_response` columns on endpoint run logs older than 14 days
- Deletes detail event rows older than 14 days
- Replaces Qualys submission request bodies with record count metadata (not full asset payloads) to limit storage

No manual action is required. The retention policy runs automatically.

## Dashboard Statistics

The **Dashboard** page shows aggregate statistics:

| Metric | Description |
|--------|-------------|
| **Total Runs** | All-time run count |
| **Success Rate** | Percentage of runs that succeeded or partially succeeded |
| **Last Sync** | Timestamp of the most recent completed run |
| **Recent Runs (24h)** | Number of runs in the last 24 hours |

## What's Next

If a run shows failures, see [[Troubleshooting]] for common issues and solutions.
