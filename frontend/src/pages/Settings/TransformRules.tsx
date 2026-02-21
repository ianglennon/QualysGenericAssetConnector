import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'

const transformRules = [
  {
    type: 'direct',
    name: 'Direct (Pass-through)',
    description: 'Copies the source field value directly to the target field without any transformation.',
    example: 'Source field "hostname" → Target field "name"',
    badge: 'Simple',
  },
  {
    type: 'static',
    name: 'Static Value',
    description: 'Uses a fixed, predefined value regardless of the source data. Useful for default values or constants.',
    example: 'Static value "Production" → Target field "environment"',
    badge: 'Default',
  },
  {
    type: 'ip_class',
    name: 'Evaluate IP Class',
    description: 'Classifies IP addresses into ranges (e.g., public, private, reserved) based on standard IP address blocks.',
    example: 'Source "192.168.1.10" → evaluates to "private" → Target field "ip_class"',
    badge: 'Network',
  },
  {
    type: 'conditional',
    name: 'If-Then-Else Conditionals',
    description: 'Applies conditional logic based on field values. Supports simple comparisons (equals, contains, greater than, etc.).',
    example: 'If source field "os" contains "Windows" then "windows" else "unix" → Target field "platform"',
    badge: 'Logic',
  },
]

export const TransformRules = () => {
  return (
    <div className="container mx-auto py-6 space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Transform Rules</h1>
        <p className="text-gray-500 mt-2">
          Available transformation rule types for field mappings. Use these rules in the Mapping Editor to transform source data before sending to Qualys.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {transformRules.map((rule) => (
          <Card key={rule.type}>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>{rule.name}</CardTitle>
                <Badge variant="outline">{rule.badge}</Badge>
              </div>
              <CardDescription>{rule.description}</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                <p className="text-sm font-medium">Example:</p>
                <code className="block p-3 bg-gray-100 dark:bg-gray-800 rounded text-sm">
                  {rule.example}
                </code>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card className="bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800">
        <CardHeader>
          <CardTitle className="text-blue-900 dark:text-blue-100">Note</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-blue-800 dark:text-blue-200">
            Transform rules are applied in the Mapping Editor when creating or editing connector field mappings. 
            See the <strong>Connectors</strong> section to configure field mappings for your data sources.
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
