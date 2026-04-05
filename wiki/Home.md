# Qualys Generic Asset Connector

A self-hosted integration platform that pulls host asset data from third-party REST APIs into Qualys CSAM (CyberSecurity Asset Management).
Operators configure connectors, map fields visually, and schedule syncs through a web UI -- no coding required.

## Get Started

1. **Deploy** -- set up Docker and environment variables ([[Getting Started]])
2. **Configure Qualys** -- connect your CSAM subscription ([[Qualys Configuration]])
3. **Create a Connector** -- point at a source REST API ([[Creating a Connector]])
4. **Run Your First Sync** -- trigger and monitor ingestion ([[Scheduling]])

## All Topics

| Page | Description |
|------|-------------|
| [[Getting Started]] | Prerequisites, environment setup, and first login |
| [[Deployment Guide]] | Production deployment, backups, TLS, and resource limits |
| [[Configuration Reference]] | Environment variables and their defaults |
| [[Creating a Connector]] | Set up a connector with authentication to a source API |
| [[Endpoints and Field Discovery]] | Configure API endpoints, pagination, and auto-detect fields |
| [[Canvases and Endpoint Chaining]] | Create data flows with parent/child endpoint trees |
| [[Field Mapping]] | Map source fields to Qualys CSAM target fields visually |
| [[Scheduling]] | Configure automated sync schedules and manual triggers |
| [[Run History and Diagnostics]] | Monitor runs, view failures, and inspect HTTP payloads |
| [[Qualys Configuration]] | Set up Qualys CSAM subscription credentials |
| [[User Management]] | Create roles, assign permissions, and manage user accounts |
| [[Architecture]] | System design, tech stack, database schema, and security model |
| [[API Reference]] | REST API endpoints for automation and integration |
| [[Troubleshooting]] | Common issues and solutions |
