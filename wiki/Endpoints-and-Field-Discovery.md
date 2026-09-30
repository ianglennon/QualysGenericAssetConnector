# Endpoints and Field Discovery

> **Workflow:** [[Creating a Connector|Connector]] > **Endpoints** > [[Canvases and Endpoint Chaining|Canvas]] > [[Field Mapping|Mapping]] > [[Scheduling|Schedule]]

Endpoints define which API resources a connector fetches. Each endpoint maps to a specific URL path on the source API. After adding an endpoint, use field discovery to inspect the response structure before building field mappings.

## Adding an Endpoint

1. Open a connector and go to the **Endpoints** tab.
2. Click **Add Endpoint**.
3. Enter an endpoint **Name** (e.g., "Hosts" or "Network Interfaces") and a **Path** relative to the connector's base URL (e.g., `/v2/hosts`). The full request URL is `{base_url}/{path}`.
4. Configure a **Data Root** if the API wraps records inside a nested object (see Data Root below). If left blank, the system auto-detects it.
5. Add a **Pagination** configuration if the API returns paginated results (see Pagination below).
6. Click **Save**.

## Endpoint Fields

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| Name | Yes | -- | Display name for the endpoint |
| Path | Yes | -- | Relative URL path, appended to connector base URL. Supports `{{variable}}` template syntax for chained endpoints. |
| Pagination | No | -- | JSON configuration for paginated APIs |
| Enabled | Yes | true | Whether this endpoint participates in syncs |

## Template Variables

Endpoint paths support `{{variable}}` template syntax for chained endpoints. When an endpoint is a child in a canvas tree, template variables are resolved from fields in the parent endpoint's records.

Example: `/api/servers/{{server_id}}/interfaces` -- for each record from the parent endpoint, `{{server_id}}` is replaced with the value of the `server_id` field from that record.

See [[Canvases and Endpoint Chaining]] for how to build parent-child trees and configure variable extraction.

## Field Discovery

Field discovery makes a sample request to the endpoint and returns the available fields from the response.

1. After saving an endpoint, click **Discover Fields**.
2. The system makes a request to the endpoint using the connector's configured authentication.
3. The response shows:
   - **Discovered fields** -- each with a dot-notation path, detected type, and a sample value from the first record
   - **Record count** -- how many records were found in the response
   - **Auto-detected data root** -- the data root the system identified (if any)

Field discovery is endpoint-scoped. Each endpoint is discovered independently using the connector's base URL and authentication.

## Array Field Annotations

Fields inside arrays receive additional annotations from field discovery:

| Annotation | Value | Meaning |
|------------|-------|---------|
| `is_array_child` | `true` | This field is nested inside an array |
| `parent_array_path` | path string | The dot-notation path to the containing array |
| `is_array_parent` | `true` | This field is itself an array of objects |

Array fields use bracket notation in their paths (e.g., `interfaces[].mac_address`). These annotations are used by the **collect** mapping type to extract values from nested arrays. See [[Field Mapping#Collect]] for details.

## Pagination

For paginated APIs, provide a JSON configuration object in the **Pagination** field. The system uses this configuration automatically during syncs to fetch all pages of data. Pagination is not used during field discovery, which only fetches the first page.

## Managing Multiple Endpoints

A connector can have any number of endpoints. Each endpoint represents a different API resource on the same source system.

**Reordering:** Drag and drop endpoints in the UI to change their display order and execution sequence.

**Delete guard:** An endpoint cannot be deleted while it is assigned to a canvas. The system returns a `409 ENDPOINT_IN_USE` error. Remove the endpoint from all canvases first, then delete it.

**Canvas assignment:** When adding endpoints to a canvas, use the `unassigned_only` filter to see which endpoints are not yet assigned to any canvas.

## What's Next

With endpoints configured and fields discovered, the next step is to create a canvas that organizes endpoints into a data flow.

[[Canvases and Endpoint Chaining]]
