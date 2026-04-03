// Must exactly mirror IDENTITY_ATTRIBUTES from backend/app/services/detection.py
export const IDENTITY_FIELDS = new Set([
  'qualysAssetId',
  'sourceNativeKey',
  'instanceUuid',
  'hostName',
  'netBiosName',
  'fqdn',
  'macAddress',
  'ipAddress',
  'serialNumber',
  'hardwareUuid',
  'networkUuid',
])
