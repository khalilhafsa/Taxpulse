import { liquidMetalFragmentShader, ShaderMount } from '@paper-design/shaders'
import { Sparkles } from 'lucide-react'
import { useEffect, useRef, useState, type MouseEvent, type ReactNode } from 'react'

/**
 * The showcase button: a ring of liquid metal (a small WebGL shader, tinted sage so it reads
 * as brushed silver-sage on the Sage Garden theme) around a deep sage face. The metal flows slowly,
 * faster on hover, and surges on click, with a ripple where you clicked. Its width follows the
 * label. Use it sparingly: one per page at most, since every instance runs its own WebGL canvas.
 * With reduced motion the metal stays still; without WebGL a static silver gradient is shown.
 */
export function LiquidMetalButton({ children, onClick, disabled = false, title, icon = true }: {
  children: ReactNode
  onClick?: () => void
  disabled?: boolean
  title?: string
  icon?: boolean
}) {
  const rim = useRef<HTMLDivElement>(null)
  const mount = useRef<ShaderMount | null>(null)
  const button = useRef<HTMLButtonElement>(null)
  const [ripples, setRipples] = useState<{ x: number; y: number; id: number }[]>([])
  const [webgl, setWebgl] = useState(true)
  const nextId = useRef(0)
  const hovered = useRef(false)
  const reduce = typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches
  const idle = reduce ? 0 : 0.5

  useEffect(() => {
    if (!rim.current) return
    try {
      mount.current = new ShaderMount(rim.current, liquidMetalFragmentShader, {
        u_colorBack: [0, 0, 0, 0],
        u_colorTint: [0.78, 0.86, 0.8, 1],
        u_repetition: 4,
        u_softness: 0.5,
        u_shiftRed: 0.3,
        u_shiftBlue: 0.3,
        u_distortion: 0,
        u_contour: 0,
        u_angle: 45,
        u_shape: 0,
        u_isImage: false,
        u_fit: 0,
        u_scale: 8,
        u_rotation: 0,
        u_offsetX: 0.1,
        u_offsetY: -0.1,
        u_originX: 0.5,
        u_originY: 0.5,
        u_worldWidth: 0,
        u_worldHeight: 0,
      }, undefined, idle)
    } catch {
      setWebgl(false)
    }
    return () => { mount.current?.dispose(); mount.current = null }
  }, [idle])

  const speed = (s: number) => { if (!reduce) mount.current?.setSpeed(s) }

  const click = (e: MouseEvent<HTMLButtonElement>) => {
    speed(2.4)
    setTimeout(() => speed(hovered.current ? 1 : idle), 320)
    const r = button.current?.getBoundingClientRect()
    if (r && !reduce) {
      const ripple = { x: e.clientX - r.left, y: e.clientY - r.top, id: nextId.current++ }
      setRipples((list) => [...list, ripple])
      setTimeout(() => setRipples((list) => list.filter((x) => x.id !== ripple.id)), 650)
    }
    onClick?.()
  }

  return (
    <button
      ref={button}
      type="button"
      title={title}
      disabled={disabled}
      onClick={click}
      onMouseEnter={() => { hovered.current = true; speed(1) }}
      onMouseLeave={() => { hovered.current = false; speed(idle) }}
      className="tp-lm group relative inline-flex min-h-11 items-center justify-center rounded-full p-[2.5px] disabled:cursor-not-allowed disabled:opacity-55"
    >
      {/* the liquid metal rim */}
      <div ref={rim} aria-hidden className={`tp-lm-rim absolute inset-0 overflow-hidden rounded-full ${webgl ? '' : 'tp-lm-static'}`} />
      {/* the sage face */}
      <span className="tp-lm-face relative z-10 inline-flex min-h-[38px] items-center gap-2 overflow-hidden rounded-full px-5 text-sm font-semibold text-white">
        {icon && <Sparkles size={15} aria-hidden className="transition-transform duration-500 group-hover:rotate-12 group-hover:scale-110" />}
        <span className="whitespace-nowrap">{children}</span>
        {ripples.map((r) => (
          <span key={r.id} aria-hidden className="tp-lm-ripple" style={{ left: r.x - 2.5, top: r.y - 2.5 }} />
        ))}
      </span>
    </button>
  )
}
