import { useState } from 'react'
import { useTheme, type ThemeMode } from '@/providers/ThemeProvider'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { toast } from '@/hooks/use-toast'

const THEME_OPTIONS: { value: ThemeMode; label: string; description: string }[] = [
  { value: 'light', label: 'Light', description: 'Clean light theme' },
  { value: 'dark', label: 'Dark', description: 'Soft dark grays' },
  { value: 'black', label: 'True Black', description: 'OLED-friendly pure black' },
  { value: 'high-contrast', label: 'High Contrast', description: 'WCAG AAA compliance' },
  { value: 'deuteranopia', label: 'Deuteranopia Mode', description: 'Red-green color blindness (blue-yellow palette)' },
  { value: 'protanopia', label: 'Protanopia Mode', description: 'Red-green color blindness (blue-yellow palette)' },
  { value: 'tritanopia', label: 'Tritanopia Mode', description: 'Blue-yellow color blindness (red-green palette)' },
  { value: 'custom', label: 'Custom', description: 'Create your own color scheme' },
]

export const ThemeCustomizer = () => {
  const { theme, setTheme, customTheme, setCustomTheme, exportTheme, importTheme } = useTheme()
  const [customColors, setCustomColors] = useState<Record<string, string>>(
    customTheme?.colors || {
      background: '0 0% 3.9%',
      foreground: '0 0% 98%',
      primary: '210 100% 50%',
      secondary: '45 100% 50%',
    }
  )

  const handleThemeChange = (value: string) => {
    setTheme(value as ThemeMode)
  }

  const handleSaveCustomTheme = () => {
    const themeName = customTheme?.name || `Custom Theme ${Date.now()}`
    setCustomTheme({
      name: themeName,
      colors: customColors,
    })
    toast({
      title: 'Success',
      description: 'Custom theme saved',
    })
  }

  const handleExport = () => {
    const themeJson = exportTheme()
    const blob = new Blob([themeJson], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `theme-${Date.now()}.json`
    a.click()
    URL.revokeObjectURL(url)
    toast({
      title: 'Success',
      description: 'Theme exported successfully',
    })
  }

  const handleImport = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (file) {
      const reader = new FileReader()
      reader.onload = (e) => {
        const content = e.target?.result as string
        const success = importTheme(content)
        if (success) {
          toast({
            title: 'Success',
            description: 'Theme imported successfully',
          })
        } else {
          toast({
            title: 'Error',
            description: 'Failed to import theme. Invalid file format.',
            variant: 'destructive',
          })
        }
      }
      reader.readAsText(file)
    }
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Theme Selection</CardTitle>
          <CardDescription>
            Choose a theme mode that works best for you. Color-blind modes use safe color palettes with pattern/icon supplementation.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="theme">Theme Mode</Label>
            <Select value={theme} onValueChange={handleThemeChange}>
              <SelectTrigger id="theme">
                <SelectValue placeholder="Select theme" />
              </SelectTrigger>
              <SelectContent>
                {THEME_OPTIONS.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    <div>
                      <div className="font-medium">{option.label}</div>
                      <div className="text-xs text-gray-500">{option.description}</div>
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {theme === 'custom' && (
            <div className="space-y-4 border-t pt-4">
              <h3 className="font-medium">Custom Colors</h3>
              <p className="text-sm text-gray-500">
                Customize theme colors using HSL format (e.g., "210 100% 50%").
              </p>
              
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="background">Background</Label>
                  <Input
                    id="background"
                    value={customColors.background || ''}
                    onChange={(e) => setCustomColors({ ...customColors, background: e.target.value })}
                    placeholder="0 0% 3.9%"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="foreground">Foreground</Label>
                  <Input
                    id="foreground"
                    value={customColors.foreground || ''}
                    onChange={(e) => setCustomColors({ ...customColors, foreground: e.target.value })}
                    placeholder="0 0% 98%"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="primary">Primary</Label>
                  <Input
                    id="primary"
                    value={customColors.primary || ''}
                    onChange={(e) => setCustomColors({ ...customColors, primary: e.target.value })}
                    placeholder="210 100% 50%"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="secondary">Secondary</Label>
                  <Input
                    id="secondary"
                    value={customColors.secondary || ''}
                    onChange={(e) => setCustomColors({ ...customColors, secondary: e.target.value })}
                    placeholder="45 100% 50%"
                  />
                </div>
              </div>

              <Button onClick={handleSaveCustomTheme}>Save Custom Theme</Button>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Import/Export</CardTitle>
          <CardDescription>
            Save your theme configuration to share across devices or with others.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-2">
            <Button onClick={handleExport} variant="outline">
              Export Theme
            </Button>
            <div>
              <Input
                id="import"
                type="file"
                accept=".json"
                onChange={handleImport}
                className="hidden"
              />
              <Button
                onClick={() => document.getElementById('import')?.click()}
                variant="outline"
              >
                Import Theme
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card className="bg-gray-50 dark:bg-gray-900">
        <CardHeader>
          <CardTitle className="text-sm">Preview</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <div className="flex gap-2">
            <div className="status-badge status-success bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-100">
              Success
            </div>
            <div className="status-badge status-warning bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-100">
              Warning
            </div>
            <div className="status-badge status-error bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-100">
              Error
            </div>
            <div className="status-badge status-info bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-100">
              Info
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
