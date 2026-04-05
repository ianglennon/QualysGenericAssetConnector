# Scheduling

> **Workflow:** [[Creating a Connector|Connector]] > [[Endpoints and Field Discovery|Endpoints]] > [[Canvases and Endpoint Chaining|Canvas]] > [[Field Mapping|Mapping]] > **Schedule**

Scheduling automates connector syncs at regular intervals. Each connector can have one schedule that triggers syncs automatically. You can also trigger syncs manually at any time.

## Setting Up a Schedule

1. Open a connector and navigate to the **Schedule** section.
2. Select an **interval type**: minutes, hours, days, or weeks.
3. Enter the **interval value** -- how often the connector should sync (for example, every 6 hours).
4. Optionally set an **execution timeout** to limit how long a sync can run.
5. Click **Save**. The schedule is created and enabled immediately. The next fire time is computed and displayed.

## Interval Ranges

Each interval type has a minimum and maximum value to prevent unreasonable schedules.

| Interval Type | Minimum | Maximum | Example |
|---------------|---------|---------|---------|
| Minutes | 5 | 1,440 | Every 30 minutes |
| Hours | 1 | 168 | Every 6 hours |
| Days | 1 | 365 | Every 2 days |
| Weeks | 1 | 52 | Every 1 week |

## Fire Time Preview

When a schedule is active, the UI displays the **next scheduled run time**. This value is computed as the current time plus the configured interval.

After each sync completes, the next fire time is recomputed from that moment. This means the schedule measures intervals from the end of the last sync, not from a fixed start point.

## Enabling and Disabling

You can pause and resume a schedule without deleting it.

1. **Pause:** Click the pause/disable toggle. This disables the schedule and clears the next run time. No syncs will fire until the schedule is resumed.
2. **Resume:** Click the resume/enable toggle. This re-enables the schedule and recomputes the next run time from the current moment plus the interval. The schedule resumes from now, not from when it was paused.

## Queueing Lock

Only one sync can run at a time per connector. If a scheduled sync fires while a previous sync is still running, the new sync is queued and will execute once the current sync completes.

This prevents duplicate data submission to Qualys and avoids resource contention.

## Task Retry

If a sync fails, the system retries automatically -- up to 3 times with a 30-second wait between attempts.

After all retries are exhausted, the sync is marked as failed in [[Run History and Diagnostics|run history]]. You can inspect the failure details there.

## Triggering a Manual Sync

You do not need a schedule to run a sync. Any connector can be synced on demand.

1. Open a connector.
2. Click the **Sync** button.
3. The sync runs immediately using the connector's current configuration.

Manual syncs use the same pipeline as scheduled syncs. The queueing lock applies -- if a sync is already running, the manual trigger is queued until the current sync completes.

## Deleting a Schedule

1. Click **Delete Schedule** to remove the schedule entirely.
2. This clears the interval configuration, disables the schedule, and removes the next run time.
3. The connector itself is not affected -- only the schedule is removed. You can set up a new schedule at any time.

## What's Next

With scheduling configured, monitor your sync results and diagnose any failures.

[[Run History and Diagnostics]]
