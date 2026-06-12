import { useEffect, useRef, useState } from "react"

const CHARS_PER_FRAME = 4

/**
 * Smooths out unevenly-sized streaming chunks by releasing characters
 * at a fixed rate via requestAnimationFrame, producing a steady typewriter effect.
 */
export function useStreamBuffer(target: string): string {
  const [displayed, setDisplayed] = useState(target)
  const ref = useRef({ target, displayed: target, running: false })

  useEffect(() => {
    // Target reset or shortened (e.g. new message) — sync immediately
    if (target.length < ref.current.displayed.length) {
      ref.current.displayed = target
      ref.current.target = target
      ref.current.running = false
      setDisplayed(target)
      return
    }

    ref.current.target = target
    if (ref.current.running) return

    const tick = () => {
      const { displayed, target } = ref.current
      if (displayed.length >= target.length) {
        ref.current.running = false
        return
      }
      const next = target.slice(0, displayed.length + CHARS_PER_FRAME)
      ref.current.displayed = next
      setDisplayed(next)
      requestAnimationFrame(tick)
    }

    ref.current.running = true
    requestAnimationFrame(tick)
  }, [target])

  return displayed
}
