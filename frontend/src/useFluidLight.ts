import { useEffect } from 'react'

/**
 * Fluid light for the Chrome theme. Instead of jumping straight to the pointer or scroll
 * position, every light value glides toward its target with exponential easing (a soft spring),
 * so reflections drift and settle like light on real metal.
 *
 * Sets on <html>:  --ax/--ay  ambient light position (px), --par parallax from scroll (px),
 *                  --shine    position of the reflection band on chrome titles (%).
 * Sets on the chrome card under the pointer: --mx/--my (px, relative to the card).
 * The loop sleeps as soon as everything has settled. Off with prefers-reduced-motion.
 */
export function useFluidLight() {
  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    const root = document.documentElement
    const target = { ax: window.innerWidth * 0.7, ay: window.innerHeight * 0.1, par: 0, shine: 0 }
    const cur = { ...target }
    let card: HTMLElement | null = null
    const cardT = { x: 0, y: 0 }
    const cardC = { x: 0, y: 0 }
    let pointerX = 0.5
    let frame = 0
    let lastT = performance.now()

    // A smooth back-and-forth (triangle wave eased by a cosine): no wrap-around jumps.
    const sweep = (t: number) => 0.5 - 0.5 * Math.cos(t * Math.PI)

    const retarget = () => {
      target.par = window.scrollY
      const t = window.scrollY / 900 + pointerX * 0.6
      target.shine = 130 - sweep(t) * 160 // band travels from beyond the right edge to beyond the left
    }

    const tick = (now: number) => {
      const dt = Math.min(64, now - lastT)
      lastT = now
      // Frame-rate independent easing: about 90% of the way in ~0.5 s for light, ~0.35 s on cards.
      const k = 1 - Math.exp(-dt / 220)
      const kc = 1 - Math.exp(-dt / 140)
      let moving = false
      for (const key of ['ax', 'ay', 'par', 'shine'] as const) {
        const d = target[key] - cur[key]
        if (Math.abs(d) > 0.05) { cur[key] += d * k; moving = true } else cur[key] = target[key]
      }
      root.style.setProperty('--ax', `${cur.ax.toFixed(1)}px`)
      root.style.setProperty('--ay', `${cur.ay.toFixed(1)}px`)
      root.style.setProperty('--par', `${cur.par.toFixed(1)}px`)
      root.style.setProperty('--shine', `${cur.shine.toFixed(2)}%`)
      if (card) {
        const dx = cardT.x - cardC.x, dy = cardT.y - cardC.y
        if (Math.abs(dx) > 0.2 || Math.abs(dy) > 0.2) { cardC.x += dx * kc; cardC.y += dy * kc; moving = true }
        card.style.setProperty('--mx', `${cardC.x.toFixed(1)}px`)
        card.style.setProperty('--my', `${cardC.y.toFixed(1)}px`)
      }
      frame = moving ? requestAnimationFrame(tick) : 0
    }
    const wake = () => { if (!frame) { lastT = performance.now(); frame = requestAnimationFrame(tick) } }

    const onMove = (e: PointerEvent) => {
      pointerX = e.clientX / Math.max(window.innerWidth, 1)
      target.ax = e.clientX
      target.ay = e.clientY
      const el = (e.target as Element | null)?.closest?.('.tp-chrome, .tp-chrome-dark') as HTMLElement | null
      if (el) {
        const r = el.getBoundingClientRect()
        if (el !== card) {
          // Entering a new card: start its light where the pointer came in, then let it glide.
          card = el
          cardC.x = e.clientX - r.left
          cardC.y = e.clientY - r.top
        }
        cardT.x = e.clientX - r.left
        cardT.y = e.clientY - r.top
      }
      retarget()
      wake()
    }
    const onScroll = () => { retarget(); wake() }

    retarget()
    cur.shine = target.shine
    wake()
    window.addEventListener('pointermove', onMove, { passive: true })
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => {
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('scroll', onScroll)
      cancelAnimationFrame(frame)
    }
  }, [])
}
