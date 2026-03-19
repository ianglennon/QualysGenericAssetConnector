import { RouterProvider } from 'react-router-dom'
import { QueryProvider } from './providers/QueryProvider'
import { ThemeProvider } from './providers/ThemeProvider'
import { Toaster } from './components/ui/toaster'
import { router } from './routes'

function App() {
  return (
    <QueryProvider>
      <ThemeProvider>
        <RouterProvider router={router} />
        <Toaster />
      </ThemeProvider>
    </QueryProvider>
  )
}

export default App
