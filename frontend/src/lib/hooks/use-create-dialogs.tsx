'use client'

import { createContext, useContext, useState, useCallback, ReactNode } from 'react'
import { AddSourceDialog } from '@/components/sources/AddSourceDialog'
import { CreateNotebookDialog } from '@/components/notebooks/CreateNotebookDialog'

// NOTE: Podcast dialog intentionally not exposed in this fork. The archival
// profile is local-only and Ollama does not serve TTS models out of the box;
// keeping the UI entry point visible only produced broken workflows. The
// backend podcast routes and the GeneratePodcastDialog component are still
// in the repo in case a future fork decides to wire a local TTS provider.

interface CreateDialogsContextType {
  openSourceDialog: () => void
  openNotebookDialog: () => void
}

const CreateDialogsContext = createContext<CreateDialogsContextType | null>(null)

export function CreateDialogsProvider({ children }: { children: ReactNode }) {
  const [sourceDialogOpen, setSourceDialogOpen] = useState(false)
  const [notebookDialogOpen, setNotebookDialogOpen] = useState(false)

  const openSourceDialog = useCallback(() => setSourceDialogOpen(true), [])
  const openNotebookDialog = useCallback(() => setNotebookDialogOpen(true), [])

  return (
    <CreateDialogsContext.Provider
      value={{
        openSourceDialog,
        openNotebookDialog,
      }}
    >
      {children}
      <AddSourceDialog open={sourceDialogOpen} onOpenChange={setSourceDialogOpen} />
      <CreateNotebookDialog open={notebookDialogOpen} onOpenChange={setNotebookDialogOpen} />
    </CreateDialogsContext.Provider>
  )
}

export function useCreateDialogs() {
  const context = useContext(CreateDialogsContext)
  if (!context) {
    throw new Error('useCreateDialogs must be used within a CreateDialogsProvider')
  }
  return context
}
