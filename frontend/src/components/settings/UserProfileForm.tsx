import { useForm } from 'react-hook-form'
import { useAuth } from '@/hooks/useAuth'
import { useChangePassword, useUpdatePreferences } from '@/hooks/queries/useUser'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { toast } from '@/hooks/use-toast'
import { useState } from 'react'

interface PasswordFormData {
  current_password: string
  new_password: string
  confirm_password: string
}

export const UserProfileForm = () => {
  const { user } = useAuth()
  const changePassword = useChangePassword()
  const updatePreferences = useUpdatePreferences()
  const [fontSize, setFontSize] = useState<'normal' | 'large' | 'x-large'>('normal')
  const [reducedMotion, setReducedMotion] = useState(false)

  const { register, handleSubmit, formState: { errors }, reset } = useForm<PasswordFormData>()

  const onPasswordChange = (data: PasswordFormData) => {
    if (data.new_password !== data.confirm_password) {
      toast({
        title: 'Error',
        description: 'New passwords do not match',
        variant: 'destructive',
      })
      return
    }

    changePassword.mutate(
      {
        current_password: data.current_password,
        new_password: data.new_password,
      },
      {
        onSuccess: () => {
          toast({
            title: 'Success',
            description: 'Password changed successfully',
          })
          reset()
        },
        onError: (error: any) => {
          toast({
            title: 'Error',
            description: error.response?.data?.detail?.error?.message || 'Failed to change password',
            variant: 'destructive',
          })
        },
      }
    )
  }

  const handleFontSizeChange = (value: string) => {
    const size = value as 'normal' | 'large' | 'x-large'
    setFontSize(size)
    updatePreferences.mutate({ font_size: size })
    
    // Apply font size to document
    document.documentElement.classList.remove('font-normal', 'font-large', 'font-x-large')
    document.documentElement.classList.add(`font-${size}`)
    
    toast({
      title: 'Success',
      description: 'Font size updated',
    })
  }

  const handleReducedMotionChange = (checked: boolean) => {
    setReducedMotion(checked)
    updatePreferences.mutate({ reduced_motion: checked })
    
    if (checked) {
      document.documentElement.classList.add('reduce-motion')
    } else {
      document.documentElement.classList.remove('reduce-motion')
    }
    
    toast({
      title: 'Success',
      description: `Reduced motion ${checked ? 'enabled' : 'disabled'}`,
    })
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>User Information</CardTitle>
          <CardDescription>Your account details</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label>Email</Label>
            <Input value={user?.email || ''} disabled />
          </div>
          <div className="space-y-2">
            <Label>Role</Label>
            <Input value={user?.role || ''} disabled className="capitalize" />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Change Password</CardTitle>
          <CardDescription>Update your account password</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit(onPasswordChange)} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="current_password">Current Password</Label>
              <Input
                id="current_password"
                type="password"
                {...register('current_password', { required: 'Current password is required' })}
              />
              {errors.current_password && (
                <p className="text-sm text-red-500">{errors.current_password.message}</p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="new_password">New Password</Label>
              <Input
                id="new_password"
                type="password"
                {...register('new_password', {
                  required: 'New password is required',
                  minLength: {
                    value: 8,
                    message: 'Password must be at least 8 characters',
                  },
                })}
              />
              {errors.new_password && (
                <p className="text-sm text-red-500">{errors.new_password.message}</p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="confirm_password">Confirm New Password</Label>
              <Input
                id="confirm_password"
                type="password"
                {...register('confirm_password', { required: 'Please confirm your password' })}
              />
              {errors.confirm_password && (
                <p className="text-sm text-red-500">{errors.confirm_password.message}</p>
              )}
            </div>

            <Button type="submit" disabled={changePassword.isPending}>
              {changePassword.isPending ? 'Changing...' : 'Change Password'}
            </Button>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Accessibility</CardTitle>
          <CardDescription>Customize your viewing experience</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="font-size">Font Size</Label>
            <Select value={fontSize} onValueChange={handleFontSizeChange}>
              <SelectTrigger id="font-size">
                <SelectValue placeholder="Select font size" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="normal">Normal</SelectItem>
                <SelectItem value="large">Large</SelectItem>
                <SelectItem value="x-large">Extra Large</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label>Reduced Motion</Label>
              <p className="text-sm text-gray-500">Minimize animations and transitions</p>
            </div>
            <input
              type="checkbox"
              checked={reducedMotion}
              onChange={(e) => handleReducedMotionChange(e.target.checked)}
              className="h-4 w-4"
            />
          </div>

          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label>Keyboard Navigation Indicators</Label>
              <p className="text-sm text-gray-500">Show focus outlines for keyboard navigation</p>
            </div>
            <input type="checkbox" defaultChecked className="h-4 w-4" />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Active Sessions</CardTitle>
          <CardDescription>Manage your active login sessions (placeholder)</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-gray-500">
            Session management will be available in a future update.
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
