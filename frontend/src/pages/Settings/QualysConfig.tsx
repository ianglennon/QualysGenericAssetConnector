import { QualysConfigForm } from '@/components/settings/QualysConfigForm'

export const QualysConfig = () => {
  return (
    <div className="container mx-auto py-6 space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Qualys Configuration</h1>
        <p className="text-gray-500 mt-2">
          Configure your Qualys CSAM subscription credentials. Credentials are encrypted and never displayed after saving.
        </p>
      </div>

      <QualysConfigForm />
    </div>
  )
}
