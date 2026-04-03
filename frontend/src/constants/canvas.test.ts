import { describe, it, expect } from 'vitest'
import { IDENTITY_FIELDS } from './canvas'

describe('IDENTITY_FIELDS', () => {
  it('is a Set with exactly 11 entries', () => {
    expect(IDENTITY_FIELDS).toBeInstanceOf(Set)
    expect(IDENTITY_FIELDS.size).toBe(11)
  })

  it.each([
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
  ])('contains %s', (field) => {
    expect(IDENTITY_FIELDS.has(field)).toBe(true)
  })
})
