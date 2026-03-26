import { useParams, useLocation, Link } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { ROUTES } from '@/routes/constants'
import type { DryRunResult } from '@/types/api'

export function DryRunResultsPage() {
  const { connectorId, canvasId } = useParams<{ connectorId: string; canvasId: string }>()
  const location = useLocation()
  const result = (location.state as { dryRunResults?: DryRunResult } | null)?.dryRunResults

  if (!result) {
    return (
      <div className="container mx-auto p-6 space-y-4">
        <Link to={ROUTES.connectorCanvas(connectorId ?? '', canvasId ?? '')}>
          <Button variant="ghost" size="sm">
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Canvas
          </Button>
        </Link>
        <Card>
          <CardHeader>
            <CardTitle>No Results Available</CardTitle>
            <CardDescription>
              No dry-run results available. Return to canvas to run a dry test.
            </CardDescription>
          </CardHeader>
        </Card>
      </div>
    )
  }

  if (result.records.length === 0) {
    return (
      <div className="container mx-auto p-6 space-y-4">
        <Link to={ROUTES.connectorCanvas(connectorId ?? '', canvasId ?? '')}>
          <Button variant="ghost" size="sm">
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Canvas
          </Button>
        </Link>
        <Card>
          <CardHeader>
            <CardTitle>No Records</CardTitle>
            <CardDescription>
              The dry run completed but produced no mapped records. Check that your
              endpoints return data and field mappings are configured.
            </CardDescription>
          </CardHeader>
        </Card>
      </div>
    )
  }

  // Derive columns from first record's keys (D-08: mapped fields only)
  const columns = Object.keys(result.records[0])

  return (
    <div className="container mx-auto p-6 space-y-4">
      <div className="flex items-center justify-between">
        <Link to={ROUTES.connectorCanvas(connectorId ?? '', canvasId ?? '')}>
          <Button variant="ghost" size="sm">
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Canvas
          </Button>
        </Link>
      </div>

      <div>
        <h1 className="text-2xl font-bold tracking-tight">Dry Run Results</h1>
        {result.capped && (
          <p className="text-sm text-muted-foreground mt-1">
            Showing 50 of {result.total_records} total records
          </p>
        )}
        {!result.capped && (
          <p className="text-sm text-muted-foreground mt-1">
            {result.total_records} record{result.total_records !== 1 ? 's' : ''}
          </p>
        )}
        {(result.records_filtered ?? 0) > 0 && (
          <p className="text-sm text-muted-foreground mt-1">
            {result.records_filtered} record{result.records_filtered !== 1 ? 's' : ''} filtered by exclusion rules
          </p>
        )}
      </div>

      <div className="border rounded-lg overflow-auto">
        <Table>
          <TableHeader>
            <TableRow>
              {columns.map(col => (
                <TableHead key={col}>{col}</TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {result.records.map((record, idx) => (
              <TableRow key={idx}>
                {columns.map(col => (
                  <TableCell key={col} className="font-mono text-xs">
                    {record[col] != null ? String(record[col]) : ''}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}
