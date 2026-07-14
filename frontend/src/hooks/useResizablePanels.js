import { useCallback, useEffect, useRef, useState } from 'react'

const STORAGE_KEY = 'roofscan.rightPanelWidth'
const MIN_RIGHT   = 300
const MAX_RIGHT   = 900
const DEFAULT_RIGHT_INITIAL   = 400  // before a result exists
const DEFAULT_RIGHT_HAS_RESULT = 480 // analysis gets more room once there's a result

const clamp = (value, min, max) => Math.max(min, Math.min(max, value))

// Desktop-only draggable divider between the map and the analysis panel.
// Lets the person drag to any width they like, or double-click to reset.
// Persists their preference across sessions.
export default function useResizablePanels(hasResult) {
  const [width, setWidth]   = useState(() => {
    const saved = Number(localStorage.getItem(STORAGE_KEY))
    return saved && saved >= MIN_RIGHT && saved <= MAX_RIGHT ? saved : null
  })
  const [dragging, setDragging] = useState(false)
  const shellRef = useRef(null)
  const draggedOnceRef = useRef(width !== null)

  // If the user never manually resized, follow the default that already
  // adapts to whether a result is showing (keeps old behaviour intact).
  const effectiveWidth = width ?? (hasResult ? DEFAULT_RIGHT_HAS_RESULT : DEFAULT_RIGHT_INITIAL)

  const onPointerDownDivider = useCallback((e) => {
    e.preventDefault()
    setDragging(true)

    const onMove = (ev) => {
      const shell = shellRef.current
      if (!shell) return
      const rect = shell.getBoundingClientRect()
      const clientX = ev.touches ? ev.touches[0].clientX : ev.clientX
      const newRightWidth = clamp(rect.right - clientX, MIN_RIGHT, MAX_RIGHT)
      setWidth(newRightWidth)
      draggedOnceRef.current = true
    }
    const onUp = () => {
      setDragging(false)
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerup', onUp)
      window.removeEventListener('touchmove', onMove)
      window.removeEventListener('touchend', onUp)
      setWidth((w) => {
        if (w != null) localStorage.setItem(STORAGE_KEY, String(w))
        return w
      })
    }

    window.addEventListener('pointermove', onMove)
    window.addEventListener('pointerup', onUp)
    window.addEventListener('touchmove', onMove, { passive: true })
    window.addEventListener('touchend', onUp)
  }, [])

  const resetWidth = useCallback(() => {
    setWidth(null)
    localStorage.removeItem(STORAGE_KEY)
    draggedOnceRef.current = false
  }, [])

  return {
    shellRef,
    dragging,
    rightWidth: effectiveWidth,
    hasCustomWidth: width !== null,
    onPointerDownDivider,
    resetWidth,
  }
}
