import { useState, useRef, useEffect } from 'react'
import { Input } from '@/components/ui/input'

interface InlineRenameProps {
  value: string
  onSave: (newName: string) => void
  onCancel: () => void
  disabled?: boolean
}

export function InlineRename({ value, onSave, onCancel, disabled }: InlineRenameProps) {
  const [text, setText] = useState(value)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    // Auto-focus and select all text
    if (inputRef.current) {
      inputRef.current.focus()
      inputRef.current.select()
    }
  }, [])

  const handleSave = () => {
    const trimmed = text.trim()
    if (!trimmed) {
      onCancel() // Empty name reverts
      return
    }
    onSave(trimmed)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      handleSave()
    } else if (e.key === 'Escape') {
      e.preventDefault()
      onCancel()
    }
  }

  return (
    <Input
      ref={inputRef}
      value={text}
      onChange={(e) => setText(e.target.value)}
      onBlur={handleSave}
      onKeyDown={handleKeyDown}
      disabled={disabled}
      placeholder="Canvas name"
      className="h-7 text-base font-semibold"
      onClick={(e) => e.stopPropagation()}
    />
  )
}
