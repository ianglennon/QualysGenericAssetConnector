import { useAuth } from '@/providers/AuthProvider'

export default function Dashboard() {
  const { user } = useAuth()

  return (
    <div className="min-h-screen p-8">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-3xl font-bold mb-4">Dashboard</h1>
        <p className="text-muted-foreground mb-6">Coming in Plan 02</p>
        
        {user && (
          <div className="bg-secondary p-6 rounded-lg border border-border">
            <h2 className="text-xl font-semibold mb-2">Current User</h2>
            <p><span className="font-medium">Email:</span> {user.email}</p>
            <p><span className="font-medium">Role:</span> {user.role}</p>
          </div>
        )}
      </div>
    </div>
  )
}
