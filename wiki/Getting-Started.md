# Getting Started

This guide walks you through first-time setup after deploying the application.

## Step 1: Log In

1. Open your browser and navigate to `http://<your-host>` (default: `http://localhost`)
2. You'll be redirected to the login page
3. Enter the admin credentials you configured in `.env` (`ADMIN_EMAIL` / `ADMIN_PASSWORD`)
4. Click **Login**

## Step 2: Configure Qualys CSAM Credentials

Before you can sync data to Qualys, you need to configure your Qualys subscription:

1. Go to **Settings > Qualys Configuration** (admin only)
2. Enter your **Qualys username** (e.g., `quays_user_us2`) -- the platform is auto-detected from the username
3. Enter the **Qualys CSAM Connector UUID** from your Qualys subscription
4. Enter your **Qualys password**
5. Click **Save**

The system auto-detects your Qualys platform (US1, US2, US3, EU1, etc.) and derives the correct API server and gateway URLs from your username.

## Step 3: Create a Connector

1. Go to **Connectors** in the sidebar
2. Click **Create Connector**
3. Fill in:
   - **Name** -- a descriptive name (e.g., "ServiceNow CMDB", "Crowdstrike Hosts")
   - **Base URL** -- the root URL of the source API (e.g., `https://api.example.com`)
   - **Auth Method** -- choose Bearer Token, Basic Auth, or API Key Header
   - **Credentials** -- enter the appropriate credentials for your chosen auth method
4. Click **Create**

See [[Creating a Connector]] for detailed instructions.

## Step 4: Add Endpoints

1. From the connector detail page, add one or more **API endpoints** (the specific paths to fetch data from)
2. Use **Discover Fields** to auto-detect available fields from the source API

See [[Endpoints and Field Discovery]] for details.

## Step 5: Create a Canvas and Map Fields

1. Create a **Canvas** (a named data flow representing one Qualys asset type)
2. Add your endpoints to the canvas (optionally chain parent/child endpoints)
3. Open the **Field Mapping** editor for each endpoint
4. Map source fields to Qualys CSAM target fields using drag-and-drop or the mapping editor

See [[Canvases and Endpoint Chaining]] and [[Field Mapping]] for details.

## Step 6: Dry Run

Before syncing to Qualys, test your configuration:

1. From the canvas page, click **Dry Run**
2. Review the transformed records to verify the mapping produces the expected output
3. Fix any issues with your field mappings

## Step 7: Run a Sync

1. From the connector detail page, click **Sync Now**
2. Monitor progress in **Run History**
3. Review the results, including per-endpoint status and any failures

See [[Scheduling]] for details.

## Step 8: Schedule Automatic Syncs (Optional)

1. From the connector detail page, configure a **Schedule**
2. Choose an interval (every N minutes, hours, days, or weeks)
3. Enable the schedule

See [[Scheduling]] for details.

## Next Steps

- [[Creating a Connector]] -- Detailed connector configuration
- [[Field Mapping]] -- All mapping types explained
- [[Canvases and Endpoint Chaining]] -- Combine data from multiple API endpoints
- [[Troubleshooting]] -- Common issues and solutions
