# Qualys Configuration

> **Setup:** [[Getting Started]] > **Qualys Configuration**

Before running any syncs, you must configure your Qualys CSAM subscription credentials.

## Setup

1. Navigate to **Settings > Qualys Configuration** (admin only)
2. Enter:

| Field | Description |
|-------|-------------|
| **Username** | Your Qualys platform username (e.g., `quays_user_us2`). The platform is auto-detected from the username |
| **Connector UUID** | The CSAM connector UUID from your Qualys subscription. Found in the Qualys CSAM connector configuration |
| **Password** | Your Qualys platform password |

3. Click **Save**

## Platform Auto-Detection

The system detects your Qualys platform from the username and automatically derives:

- **API Server URL** -- the Qualys API server for your platform
- **API Gateway URL** -- the Qualys API gateway for your platform

Supported platforms include US1, US2, US3, US4, EU1, EU2, IN1, CA1, AE1, and others. The platform identifier is extracted from the username format.

## Singleton Configuration

Only one Qualys configuration can exist at a time. Saving new credentials replaces the existing configuration.

## Password Handling

- Password is **required** on initial setup
- On subsequent updates, if the password field is left empty, the existing encrypted password is preserved
- The password is Fernet-encrypted before storage and never returned in API responses

## Verifying Configuration

After saving, the configuration page shows:
- Platform name
- API Server URL
- API Gateway URL
- Whether a password is configured (`has_password: true`)

## Permissions

Only **admin** users can view or modify Qualys configuration.

## Pre-flight Validation

Before each sync run, the system validates that:
1. Qualys configuration exists
2. The encrypted password can be decrypted

If either check fails, the run is marked as failed with a descriptive error.

## Credential Issues

If Qualys credentials are invalid or expired, sync runs fail with a `QUALYS_NOT_CONFIGURED` or authentication error. The run detail page shows the specific error message.

For diagnosis steps, see [[Troubleshooting]].

## What's Next

With Qualys configured, you're ready to create connectors and map source data to Qualys fields.

[[Creating a Connector]]
