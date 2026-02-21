import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { UserProfileForm } from '@/components/settings/UserProfileForm'
import { ThemeCustomizer } from '@/components/settings/ThemeCustomizer'

export const UserProfile = () => {
  return (
    <div className="container mx-auto py-6 space-y-6">
      <div>
        <h1 className="text-3xl font-bold">User Profile</h1>
        <p className="text-gray-500 mt-2">
          Manage your account settings, theme preferences, and accessibility options.
        </p>
      </div>

      <Tabs defaultValue="profile" className="w-full">
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="profile">Profile</TabsTrigger>
          <TabsTrigger value="theme">Theme</TabsTrigger>
        </TabsList>

        <TabsContent value="profile" className="mt-6">
          <UserProfileForm />
        </TabsContent>

        <TabsContent value="theme" className="mt-6">
          <ThemeCustomizer />
        </TabsContent>
      </Tabs>
    </div>
  )
}
