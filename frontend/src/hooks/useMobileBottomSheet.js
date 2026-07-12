import { useEffect, useRef, useState } from 'react'

const MOBILE_BREAKPOINT = 912
const MIN_HEIGHT = 72

const clamp = (value, min, max) => Math.max(min, Math.min(max, value))

export default function useMobileBottomSheet() {
  const [isMobileSheet, setIsMobileSheet] = useState(false)
  const [sheetHeight, setSheetHeight] = useState(0)
  const dragStartYRef = useRef(0)
  const dragStartHeightRef = useRef(0)

  const getMinHeight = () => MIN_HEIGHT

  const getMaxHeight = () => {
    const header = document.querySelector('.app-header')
    const headerBottom = header?.getBoundingClientRect().bottom ?? 0
    const maxAllowed = Math.floor(window.innerHeight - headerBottom)
    return Math.max(220, maxAllowed)
  }

  const getSnapHeight = (currentHeight) => {
    const min = getMinHeight()
    const max = getMaxHeight()
    const mid = Math.round((min + max) / 2)
    const snaps = [min, mid, max]
    return snaps.reduce((closest, candidate) =>
      Math.abs(candidate - currentHeight) < Math.abs(closest - currentHeight)
        ? candidate
        : closest
    , snaps[0])
  }

  useEffect(() => {
    const updateLayout = () => {
      const mobile = window.innerWidth <= MOBILE_BREAKPOINT
      setIsMobileSheet(mobile)
      if (mobile) {
        const defaultHeight = Math.round(window.innerHeight * 0.6)
        setSheetHeight((prev) => {
          const min = getMinHeight()
          const max = getMaxHeight()
          if (!prev) return clamp(defaultHeight, min, max)
          return clamp(prev, min, max)
        })
      }
    }

    updateLayout()
    window.addEventListener('resize', updateLayout)
    return () => window.removeEventListener('resize', updateLayout)
  }, [])

  const startDrag = (clientY) => {
    dragStartYRef.current = clientY
    dragStartHeightRef.current = sheetHeight
  }

  const dragTo = (clientY) => {
    if (!isMobileSheet) return
    const deltaY = clientY - dragStartYRef.current
    const nextHeight = clamp(
      dragStartHeightRef.current - deltaY,
      getMinHeight(),
      getMaxHeight()
    )
    setSheetHeight(nextHeight)
  }

  const finishDrag = () => {
    setSheetHeight((prev) => getSnapHeight(prev))
  }

  const handlePointerDown = (e) => {
    if (!isMobileSheet) return
    e.currentTarget.setPointerCapture?.(e.pointerId)
    startDrag(e.clientY)

    const onMove = (ev) => dragTo(ev.clientY)
    const onUp = () => {
      finishDrag()
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerup', onUp)
    }

    window.addEventListener('pointermove', onMove)
    window.addEventListener('pointerup', onUp)
  }

  const handleTouchStart = (e) => {
    if (!isMobileSheet) return
    const touch = e.touches[0]
    if (!touch) return
    startDrag(touch.clientY)

    const onMove = (ev) => {
      const t = ev.touches[0]
      if (!t) return
      dragTo(t.clientY)
    }
    const onEnd = () => {
      finishDrag()
      window.removeEventListener('touchmove', onMove)
      window.removeEventListener('touchend', onEnd)
    }

    window.addEventListener('touchmove', onMove, { passive: true })
    window.addEventListener('touchend', onEnd)
  }

  const sheetStyle = isMobileSheet
    ? { height: `${sheetHeight}px`, maxHeight: `${sheetHeight}px`, bottom: '0px' }
    : undefined

  return { isMobileSheet, sheetStyle, handlePointerDown, handleTouchStart }
}
