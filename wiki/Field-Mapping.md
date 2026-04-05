# Field Mapping

> **Workflow:** [[Creating a Connector|Connector]] > [[Endpoints and Field Discovery|Endpoints]] > [[Canvases and Endpoint Chaining|Canvas]] > **Mapping** > [[Scheduling|Schedule]]

Field mapping defines how source API fields are transformed into Qualys CSAM target fields. Each endpoint in a canvas has its own set of mappings. The visual canvas provides a drag-and-connect interface for creating mappings.

## Using the Visual Canvas

1. Open a canvas and select an endpoint.
2. Source fields (discovered from the API) appear on the left; Qualys target fields appear on the right.
3. Drag from a source field to a target field to create a `direct_copy` mapping.
4. Click the type badge on a mapping to cycle through mapping types: direct_copy, static_default, conditional, collect.
5. Click a mapping to open the editor dialog for that type.
6. To delete a mapping, use the delete action on the mapping row.
7. Click **Save** to persist all mappings for this endpoint. Save performs an atomic batch replace -- all mappings for the endpoint are replaced in a single transaction.

## Mapping Types

### Direct Copy

**What it does:** Copies a source field value directly to a Qualys target field with no transformation.

**When to use it:** The source field maps 1:1 to a Qualys field and the value can be used as-is.

**Configuration fields:**

| Field | Required | Description |
|-------|----------|-------------|
| `source_field` | Yes | The source API field to read from. |
| `target_field` | Yes | The Qualys CSAM field to write to. |

**Example:** Map `hostname` to `hostName` -- the source value is copied directly.

### Static Default

**What it does:** Always uses a fixed value regardless of the source data.

**When to use it:** You need a constant value for every record, such as an asset type label or a data source identifier.

**Configuration fields:**

| Field | Required | Description |
|-------|----------|-------------|
| `static_value` | Yes | The constant value to use for every record. |
| `target_field` | Yes | The Qualys CSAM field to write to. |

**Example:** Set `assetType` to `"Server"` for all records from this endpoint.

### Conditional

**What it does:** Evaluates conditions against source fields to determine the target value. Conditions are evaluated in order; the first match wins.

**When to use it:** The target value depends on the content of a source field -- for example, mapping an OS family based on the OS name string.

**Configuration fields:**

| Field | Required | Description |
|-------|----------|-------------|
| `conditions[]` | Yes | List of condition rules (see below). |
| `fallback` | No | Value to use if no conditions match. |
| `target_field` | Yes | The Qualys CSAM field to write to. |

Each condition rule contains:

| Field | Description |
|-------|-------------|
| `operator` | Comparison operator (see operator list below). |
| `source_field` | The source API field to evaluate. |
| `target_value` | The value to compare against (string or list for `in_list`). |
| `value` | The output value when this condition matches. |

**Operators:** `equals`, `not_equals`, `contains`, `starts_with`, `ends_with`, `regex`, `in_list`

**Example:** If `os_name` contains `"Windows"`, set `osFamily` to `"Windows"`. Otherwise, fall back to `"Linux"`.

### Collect

**What it does:** Aggregates values from a nested array in the source data into a single target field.

**When to use it:** The source data contains arrays -- such as a list of IP addresses, tags, or software entries -- that need to be flattened into one field value.

**Configuration fields:**

| Field | Required | Description |
|-------|----------|-------------|
| `array_path` | Yes | Dot-notation path to the array in the source data (e.g., `network.ip_addresses`). |
| `extract_field` | No | Specific field to extract from each array element. If omitted, uses the element value directly. |
| `collect_filter` | No | Filter to apply before collecting. Contains `field`, `operator`, and `value`. Uses the same operators as conditional mappings. |
| `separator` | No | Delimiter for joining collected values (e.g., `,`). |
| `target_field` | Yes | The Qualys CSAM field to write to. |

**Example:** Collect all values from `ip_addresses[].address`, separated by comma, into `ipAddress`. To collect only IPv4 addresses, add a filter where `type` equals `"ipv4"`.

## Save Flow

Saving triggers an atomic batch replace via PUT -- all mappings for the endpoint are replaced in a single transaction. There is no partial save.

After save, two validations run automatically:

1. **Base endpoint detection** -- BFS re-evaluates which endpoint is the identity anchor based on the current mappings. See [[Canvases and Endpoint Chaining#How It Works]] for how base detection works.
2. **Cross-endpoint collision validation** -- If the same Qualys target field is mapped in multiple endpoints within the same canvas, a collision error is raised.

**Identity field gate:** A canvas cannot execute until at least one identity attribute is mapped on an endpoint. The identity attributes determine which endpoint becomes the base. Until an identity field is mapped, the canvas is considered invalid.

## Collision Validation

The same Qualys target field cannot be mapped in more than one endpoint within the same canvas. This prevents ambiguous data -- each target field must have a single source.

Collisions are detected on save and reported as validation errors. To resolve a collision, remove the duplicate mapping from one endpoint, or move it to the correct endpoint in the tree.

## What's Next

With field mappings configured, the next step is to schedule automatic syncs.

[[Scheduling]]
