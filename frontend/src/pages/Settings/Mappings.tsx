import { useState } from 'react'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { MappingCanvas } from '@/components/mappings/MappingCanvas'
import { useConnectors } from '@/hooks/queries/useConnectors'

export default function Mappings() {
  const [selectedConnectorId, setSelectedConnectorId] = useState<string>('')
  const { data: connectors, isLoading } = useConnectors()

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Field Mappings</h1>
        <p className="text-muted-foreground mt-2">
          Configure how source fields are mapped to Qualys CSAM asset fields
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Select Connector</CardTitle>
          <CardDescription>
            Choose a connector to configure its field mappings
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <Skeleton className="h-10 w-full" />
          ) : (
            <Select value={selectedConnectorId} onValueChange={setSelectedConnectorId}>
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Select a connector..." />
              </SelectTrigger>
              <SelectContent>
                {connectors?.map((connector) => (
                  <SelectItem key={connector.id} value={connector.id}>
                    {connector.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        </CardContent>
      </Card>

      {selectedConnectorId && (
        <Card>
          <CardHeader>
            <CardTitle>Field Mapping Canvas</CardTitle>
            <CardDescription>
              Drag from source fields on the left to Qualys target fields on the right to create mappings
            </CardDescription>
          </CardHeader>
          <CardContent className="h-[600px]">
            <MappingCanvas connectorId={selectedConnectorId} />
          </CardContent>
        </Card>
      )}
    </div>
  )
}
