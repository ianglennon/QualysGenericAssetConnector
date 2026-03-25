/**
 * ROUTES — single source of truth for all navigation paths.
 *
 * Usage convention:
 *   - Static paths (e.g. ROUTES.DASHBOARD) are absolute paths with a leading slash.
 *     Use them directly in <Link to={ROUTES.DASHBOARD}> or navigate(ROUTES.DASHBOARD).
 *   - Helper functions (e.g. ROUTES.connectorDetail(id)) return absolute paths.
 *   - React Router `path:` config values use relative segments without a leading slash
 *     (e.g. 'dashboard', 'runs/:id'). Do NOT use ROUTES constants for those values.
 *   - If you need the relative segment from a ROUTES constant, use .slice(1).
 */
export const ROUTES = {
  LOGIN: '/login',
  DASHBOARD: '/dashboard',
  CONNECTORS: '/connectors',
  RUNS: '/runs',
  PROFILE: '/profile',
  SETTINGS: '/settings',
  SETTINGS_QUALYS: '/settings/qualys',
  SETTINGS_TRANSFORM_RULES: '/settings/transform-rules',

  /** Returns the absolute path to a connector's detail page. */
  connectorDetail: (id: string | number): string => `/connectors/${id}`,

  /** Returns the absolute path to an endpoint's field mappings page. */
  connectorMappings: (connectorId: string | number, endpointId: string | number): string =>
    `/connectors/${connectorId}/endpoints/${endpointId}/mappings`,

  /** Returns the absolute path to a connector's canvas page. */
  connectorCanvas: (connectorId: string | number, canvasId: string | number): string =>
    `/connectors/${connectorId}/canvases/${canvasId}`,

  /** Returns the absolute path to a run's detail page. */
  runDetail: (id: string | number): string => `/runs/${id}`,
} as const
