import { useState } from 'react'
import { Plus } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { PageContainer } from '@/components/layout/PageContainer'
import { ConnectorList } from '@/components/connectors/ConnectorList'
import { ConnectorWizard } from '@/components/connectors/ConnectorWizard'
import { useConnectors, useCreateConnector, useUpdateConnector, useDeleteConnector } from '@/hooks/queries/useConnectors'
import { useTriggerRun } from '@/hooks/queries/useRuns'
import { useAuth } from '@/hooks/useAuth'
import { useToast } from '@/hooks/use-toast'
import type { Connector, ConnectorCreate } from '@/types/api'

export function ConnectorListPage() {
  const { user } = useAuth()
  const { data: connectors, isLoading } = useConnectors()
  const createMutation = useCreateConnector()
  const updateMutation = useUpdateConnector()
  const deleteMutation = useDeleteConnector()
  const triggerRunMutation = useTriggerRun()
  const { toast } = useToast()

  const [isCreateOpen, setIsCreateOpen] = useState(false)
  const [isEditOpen, setIsEditOpen] = useState(false)
  const [isDeleteOpen, setIsDeleteOpen] = useState(false)
  const [selectedConnector, setSelectedConnector] = useState<Connector | null>(null)
  const [syncSuccessId, setSyncSuccessId] = useState<string | null>(null)

  const isAdmin = user?.role === 'admin'

  const handleCreate = async (data: ConnectorCreate) => {
    try {
      await createMutation.mutateAsync(data)
      setIsCreateOpen(false)
      toast({
        title: 'Connector created',
        description: `${data.name} has been created successfully.`,
      })
    } catch (error: any) {
      toast({
        title: 'Failed to create connector',
        description: error.response?.data?.detail?.message || 'An error occurred',
        variant: 'destructive',
      })
    }
  }

  const handleEdit = (connector: Connector) => {
    setSelectedConnector(connector)
    setIsEditOpen(true)
  }

  const handleUpdate = async (data: ConnectorCreate) => {
    if (!selectedConnector) return

    try {
      await updateMutation.mutateAsync({ id: selectedConnector.id, connector: data })
      setIsEditOpen(false)
      setSelectedConnector(null)
      toast({
        title: 'Connector updated',
        description: `${data.name} has been updated successfully.`,
      })
    } catch (error: any) {
      toast({
        title: 'Failed to update connector',
        description: error.response?.data?.detail?.message || 'An error occurred',
        variant: 'destructive',
      })
    }
  }

  const handleDeleteClick = (connector: Connector) => {
    setSelectedConnector(connector)
    setIsDeleteOpen(true)
  }

  const handleDeleteConfirm = async () => {
    if (!selectedConnector) return

    try {
      await deleteMutation.mutateAsync(selectedConnector.id)
      setIsDeleteOpen(false)
      setSelectedConnector(null)
      toast({
        title: 'Connector deleted',
        description: `${selectedConnector.name} has been deleted successfully.`,
      })
    } catch (error: any) {
      toast({
        title: 'Failed to delete connector',
        description: error.response?.data?.detail?.message || 'An error occurred',
        variant: 'destructive',
      })
    }
  }

  const handleTriggerSync = async (connector: Connector) => {
    try {
      await triggerRunMutation.mutateAsync(connector.id)
      setSyncSuccessId(connector.id)
      setTimeout(() => setSyncSuccessId(null), 3000)
    } catch (error: unknown) {
      const axiosError = error as { response?: { data?: { error?: { message?: string } } } }
      const message = axiosError.response?.data?.error?.message ?? 'An unexpected error occurred'
      toast({
        title: 'Sync failed',
        description: message,
        variant: 'destructive',
      })
    }
  }

  return (
    <>
      <PageContainer
        title="Connectors"
        actions={
          isAdmin ? (
            <Button onClick={() => setIsCreateOpen(true)}>
              <Plus className="mr-2 h-4 w-4" />
              Create Connector
            </Button>
          ) : undefined
        }
      >
        <ConnectorList
          connectors={connectors}
          isLoading={isLoading}
          onEdit={isAdmin ? handleEdit : undefined}
          onDelete={isAdmin ? handleDeleteClick : undefined}
          onTriggerSync={handleTriggerSync}
          syncSuccessId={syncSuccessId}
        />
      </PageContainer>

      {/* Create Dialog */}
      <Dialog open={isCreateOpen} onOpenChange={setIsCreateOpen}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Create Connector</DialogTitle>
          </DialogHeader>
          <ConnectorWizard
            onSubmit={handleCreate}
            isSubmitting={createMutation.isPending}
          />
        </DialogContent>
      </Dialog>

      {/* Edit Dialog */}
      <Dialog open={isEditOpen} onOpenChange={setIsEditOpen}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Edit Connector</DialogTitle>
          </DialogHeader>
          {selectedConnector && (
            <ConnectorWizard
              connector={selectedConnector}
              onSubmit={handleUpdate}
              isSubmitting={updateMutation.isPending}
            />
          )}
        </DialogContent>
      </Dialog>

      {/* Delete Dialog */}
      <Dialog open={isDeleteOpen} onOpenChange={setIsDeleteOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Connector</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Are you sure you want to delete <strong>{selectedConnector?.name}</strong>?
              This action cannot be undone and will also delete all associated field mappings.
            </p>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setIsDeleteOpen(false)}>
                Cancel
              </Button>
              <Button
                variant="destructive"
                onClick={handleDeleteConfirm}
                disabled={deleteMutation.isPending}
              >
                Delete
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}
