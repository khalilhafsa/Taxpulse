import { useEffect, useRef, useState, type ReactNode } from 'react'
import type { Pipeline, Stage } from '../api'

/*
 * The agent chain as a small office team. Each AI agent is a person at a desk; the pre-filter,
 * which is plain code, is a little sorting machine. Everyone blinks and breathes. The one whose
 * turn it is works at the desk, says what they are on, and files arrive from the previous desk;
 * when they finish, they cheer and the turn passes on. Accepted alerts wait at your desk (the
 * heat gate) before the last two agents can start.
 */

export const W = 1200
const H = 250
export const X = [100, 300, 500, 700, 900, 1100]
const GATE = 800
const DESK = 172 // desk top

const C = {
  brand: '#5b6b3e', brandDark: '#364121', navy: '#3d4a5c', slate: '#6b7280', ink: '#1a1f2e',
  heat: '#a8641c', heatSoft: '#f6ead8', desk: '#e4e6df', deskTop: '#cfd4c8', shirt: '#ffffff',
}

type Look = {
  skin: string; hair: string; jacket: string; hairPath: string; extra?: ReactNode
}

// Original, simple characters. Hair paths are drawn around a head centred at (0, 96), radius 20.
const LOOKS: Record<string, Look> = {
  profiler: {
    skin: '#f1c9a5', hair: '#4a3426', jacket: C.brand,
    hairPath: 'M-21 98 C-24 72 -8 68 0 68 C14 68 24 76 21 98 L21 108 C18 104 17 92 14 86 C6 92 -10 92 -16 86 C-18 94 -18 104 -21 108 Z',
    extra: (
      <g fill="none" stroke={C.ink} strokeWidth="1.4">
        <circle cx="-7.5" cy="96" r="5.2" /><circle cx="7.5" cy="96" r="5.2" /><path d="M-2.3 96h4.6" />
      </g>
    ),
  },
  analyst: {
    skin: '#c68a5e', hair: '#1f1a17', jacket: C.navy,
    hairPath: 'M-20 92 C-21 74 -6 70 2 71 C16 72 22 80 20 92 C16 84 8 81 0 82 C-8 82 -16 85 -20 92 Z',
  },
  matcher: {
    skin: '#e8b48f', hair: '#8a3b1e', jacket: C.slate,
    hairPath: 'M-20 96 C-22 76 -8 72 0 72 C10 72 22 77 20 96 C16 86 10 82 0 82 C-10 82 -16 87 -20 96 Z',
    extra: <circle cx="0" cy="69" r="8.5" fill="#8a3b1e" />,
  },
  explainer: {
    skin: '#8d5a3b', hair: '#b9b4ad', jacket: C.brandDark,
    hairPath: 'M-20 90 C-20 76 -8 73 0 73 C10 73 20 76 20 90 C14 84 6 82 0 82 C-6 82 -14 84 -20 90 Z',
    extra: <path d="M-12 104 C-10 116 10 116 12 104 C8 110 -8 110 -12 104 Z" fill="#b9b4ad" />,
  },
  writer: {
    skin: '#f3d2b8', hair: '#2e2a26', jacket: C.brand,
    hairPath: 'M-21 94 C-26 82 -16 68 -4 70 C2 64 14 66 16 74 C24 76 26 88 21 94 C18 86 12 82 0 83 C-10 83 -18 87 -21 94 Z',
  },
}

function DeskItem({ k }: { k: string }) {
  switch (k) {
    case 'profiler': // stack of client files
      return (
        <g transform="translate(-40 152)">
          <rect y="12" width="26" height="7" rx="1.5" fill="#e3c98f" stroke="#b49a5f" />
          <rect x="2" y="6" width="26" height="7" rx="1.5" fill="#dfe6dc" stroke="#8b9d83" />
          <rect x="-1" width="26" height="7" rx="1.5" fill="#e3c98f" stroke="#b49a5f" />
        </g>
      )
    case 'analyst': // the BMF letter, paragraph sign
      return (
        <g transform="translate(-42 146) rotate(-6)">
          <rect width="22" height="27" rx="2" fill="#fff" stroke="#9aa3ad" />
          <text x="11" y="18" textAnchor="middle" fontSize="14" fontWeight="700" fill={C.navy} fontFamily="Georgia, serif">§</text>
        </g>
      )
    case 'matcher': // balance scales
      return (
        <g transform="translate(-36 146)" stroke={C.ink} strokeWidth="1.4" fill="none">
          <path d="M0 24h14M7 24V3M-4 6h22" />
          <path d="M-4 6l-4 9h8zM18 6l-4 9h8z" fill="#f1e2b8" />
        </g>
      )
    case 'explainer': // memo and pen
      return (
        <g transform="translate(-44 156)">
          <rect width="26" height="15" rx="1.5" fill="#fff" stroke="#9aa3ad" />
          <path d="M4 5h18M4 9h13" stroke="#9aa3ad" />
          <path d="M18 -6l9 14" stroke={C.heat} strokeWidth="2.4" strokeLinecap="round" />
        </g>
      )
    case 'writer': // envelope
      return (
        <g transform="translate(-44 155)">
          <rect width="26" height="17" rx="2" fill="#fff" stroke="#9aa3ad" />
          <path d="M1 2l12 8 12-8" fill="none" stroke="#9aa3ad" />
        </g>
      )
    default:
      return null
  }
}

/** Blink: eyes squash shut for a moment, at a rhythm that differs per person. */
function Eyes({ i, mode, reduce }: { i: number; mode: 'sleep' | 'work' | 'idle' | 'happy'; reduce: boolean }) {
  if (mode === 'sleep' || mode === 'happy') {
    const d = mode === 'sleep' ? 'q2.5 2.5 5 0' : 'q2.5 -3 5 0'
    return (
      <g fill="none" stroke={C.ink} strokeWidth="1.6" strokeLinecap="round">
        <path d={`M-10 96 ${d}`} /><path d={`M5 96 ${d}`} />
      </g>
    )
  }
  const dur = `${3.6 + i * 0.7}s`
  const look = mode === 'work' ? 2 : 0
  return (
    <g fill={C.ink}>
      {[-7.5, 7.5].map((x) => (
        <ellipse key={x} cx={x} cy={96 + look} rx="2" ry="2.4">
          {!reduce && <animate attributeName="ry" values="2.4;2.4;0.3;2.4" keyTimes="0;0.94;0.97;1" dur={dur} repeatCount="indefinite" />}
        </ellipse>
      ))}
    </g>
  )
}

function Person({ k, i, mode, reduce, cheer }: {
  k: string; i: number; mode: 'sleep' | 'work' | 'idle' | 'happy'; reduce: boolean; cheer: boolean
}) {
  const L = LOOKS[k]
  const working = mode === 'work'
  return (
    <g>
      {/* body and head breathe together */}
      <g>
        {!reduce && (
          <animateTransform attributeName="transform" type="translate" values="0 0;0 -1.4;0 0"
            dur={`${3.2 + i * 0.3}s`} repeatCount="indefinite" />
        )}
        {cheer && !reduce && (
          <animateTransform attributeName="transform" type="translate" additive="sum"
            values="0 0;0 -10;0 0;0 -6;0 0" dur="0.9s" fill="freeze" />
        )}
        <g transform={mode === 'sleep' ? 'rotate(8 0 140)' : undefined}>
          {/* torso */}
          <path d="M-30 176 C-30 138 -22 124 0 124 C22 124 30 138 30 176 Z" fill={L.jacket} />
          <path d="M-9 124 L0 142 L9 124 Z" fill={C.shirt} />
          <path d="M-9 124 L-3 150 L0 142 Z M9 124 L3 150 L0 142 Z" fill="#000" opacity="0.12" />
          <rect x="-5" y="113" width="10" height="12" rx="3" fill={L.skin} />
          {/* head */}
          <circle cx="0" cy="96" r="20" fill={L.skin} />
          <path d={L.hairPath} fill={L.hair} />
          <Eyes i={i} mode={mode} reduce={reduce} />
          <circle cx="-12" cy="104" r="3.2" fill="#e8796b" opacity="0.22" />
          <circle cx="12" cy="104" r="3.2" fill="#e8796b" opacity="0.22" />
          {L.extra}
          <path d={mode === 'happy' || cheer ? 'M-6 105 Q0 111 6 105' : working ? 'M-3.5 107 Q0 108.5 3.5 107' : 'M-5 106 Q0 109.5 5 106'}
            fill="none" stroke={C.ink} strokeWidth="1.6" strokeLinecap="round" />
        </g>
      </g>
      {/* hands on the desk: typing while working */}
      {[-15, 15].map((x, n) => (
        <g key={x}>
          <ellipse cx={x} cy={DESK - 3} rx="7" ry="4.5" fill={L.skin} stroke="#000" strokeOpacity="0.08">
            {working && !reduce && (
              <animate attributeName="cy" values={`${DESK - 3};${DESK - 8};${DESK - 3}`} dur="0.42s"
                begin={`${n * 0.21}s`} repeatCount="indefinite" />
            )}
          </ellipse>
        </g>
      ))}
      {/* sleeping: floating z's */}
      {mode === 'sleep' && !reduce && [0, 1].map((n) => (
        <text key={n} x="20" y="78" fontSize={11 + n * 3} fill="#a8a29e" fontWeight="600" fontFamily="Public Sans, sans-serif" opacity="0">
          z
          <animateTransform attributeName="transform" type="translate" values="0 0;10 -24" dur="2.6s" begin={`${n * 1.3}s`} repeatCount="indefinite" />
          <animate attributeName="opacity" values="0;.8;0" dur="2.6s" begin={`${n * 1.3}s`} repeatCount="indefinite" />
        </text>
      ))}
    </g>
  )
}

/** The pre-filter is code, not a person: a small sorting machine that drops pairs with no shared tax area. */
function Sorter({ mode, reduce }: { mode: 'sleep' | 'work' | 'idle' | 'happy'; reduce: boolean }) {
  const on = mode === 'work'
  return (
    <g>
      <path d="M-26 92 h52 l-14 20 h-24 Z" fill="#dfe6dc" stroke={C.brand} strokeWidth="1.5" strokeLinejoin="round" />
      <rect x="-26" y="112" width="52" height="58" rx="8" fill="#f2f5f0" stroke={C.brand} strokeWidth="1.5" />
      <rect x="-15" y="124" width="30" height="16" rx="4" fill={C.brandDark} />
      {[-6, 6].map((x) => (
        <circle key={x} cx={x} cy="132" r="2.6" fill={on ? '#a0aa88' : mode === 'sleep' ? '#78716c' : '#ced4bf'}>
          {on && !reduce && <animate attributeName="opacity" values="1;.3;1" dur="0.6s" repeatCount="indefinite" />}
        </circle>
      ))}
      <rect x="-12" y="152" width="24" height="5" rx="2.5" fill={C.brand} opacity=".35" />
      {on && !reduce && [0, 1].map((n) => (
        <use key={n} href="#tp-sheet" width="11" height="14" x="-5" y="150" opacity="0">
          <animateTransform attributeName="transform" type="translate" values="0 0;26 34" dur="1.4s" begin={`${n * 0.7}s`} repeatCount="indefinite" />
          <animate attributeName="opacity" values="0;1;0" dur="1.4s" begin={`${n * 0.7}s`} repeatCount="indefinite" />
        </use>
      ))}
    </g>
  )
}

export type TeamProps = {
  p: Pipeline
  busyKeys: Set<string>
  finished: Set<string>
  handoff: { from: number; to: number; id: number } | null
  reduce: boolean
}

export function Team({ p, busyKeys, finished, handoff, reduce }: TeamProps) {
  const pile = Math.min(p.waiting_for_review, 6)
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="block h-auto w-full" role="img"
      aria-label={busyKeys.size ? `At work: ${p.stages.filter((s) => busyKeys.has(s.key)).map((s) => s.name).join(', ')}` : 'The agent team, waiting for new work'}>
      <defs>
        <symbol id="tp-sheet" viewBox="0 0 10 13">
          <path d="M1 .5h5.5L9 3v9.5H1z" fill="#fff" stroke={C.brand} strokeWidth="1" strokeLinejoin="round" />
          <path d="M3 6h4M3 8.5h4" stroke={C.brand} strokeWidth=".8" strokeOpacity=".6" />
        </symbol>
        <symbol id="tp-sheet-heat" viewBox="0 0 10 13">
          <path d="M1 .5h5.5L9 3v9.5H1z" fill={C.heatSoft} stroke={C.heat} strokeWidth="1" strokeLinejoin="round" />
          <path d="M3 6h4M3 8.5h4" stroke={C.heat} strokeWidth=".8" strokeOpacity=".7" />
        </symbol>
        <radialGradient id="tp-spot" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor={C.brand} stopOpacity="0.22" />
          <stop offset="100%" stopColor={C.brand} stopOpacity="0" />
        </radialGradient>
      </defs>

      {/* floor */}
      <line x1="0" x2={W} y1="216" y2="216" stroke="#dfe2da" strokeWidth="2" />

      {/* your desk: the review gate */}
      <g>
        <line x1={GATE} x2={GATE} y1="40" y2="216" stroke={C.heat} strokeWidth="1.5" strokeDasharray="5 5" />
        <rect x={GATE - 34} y="190" width="68" height="24" rx="12" fill={C.heatSoft} stroke={C.heat} />
        <text x={GATE} y="206" textAnchor="middle" fontSize="12" fontWeight="600" fill={C.heat} fontFamily="Public Sans, sans-serif">You</text>
        {Array.from({ length: pile }, (_, i) => (
          <use key={i} href="#tp-sheet-heat" x={GATE - 8 + (i % 2) * 3} y={168 - i * 7} width="15" height="19" />
        ))}
        {p.waiting_for_review > 0 && (
          <text x={GATE} y="34" textAnchor="middle" fontSize="12" fontWeight="600" fill={C.heat} fontFamily="Public Sans, sans-serif">
            {p.waiting_for_review} waiting for you
          </text>
        )}
      </g>

      {p.stages.map((s, i) => {
        const at = busyKeys.has(s.key)
        const done = s.total > 0 && s.done >= s.total
        const mode = at ? 'work' : s.runs === 0 && s.done === 0 && s.llm ? 'sleep' : done ? 'idle' : 'idle'
        const cheer = finished.has(s.key)
        return (
          <g key={s.key} transform={`translate(${X[i]} 0)`}>
            {at && <ellipse cx="0" cy="214" rx="78" ry="16" fill="url(#tp-spot)" />}
            {s.llm ? (
              <>
                <Person k={s.key} i={i} mode={cheer ? 'happy' : mode} reduce={reduce} cheer={cheer} />
                {/* desk */}
                <rect x="-50" y={DESK} width="100" height="8" rx="3" fill={C.deskTop} />
                <rect x="-46" y={DESK + 8} width="92" height="34" rx="2" fill={C.desk} />
                <DeskItem k={s.key} />
                {/* laptop */}
                <path d={`M8 ${DESK} l4 -22 h30 l-4 22 Z`} fill="#c9d1d3" stroke="#9aa6a9" />
                <circle cx="25" cy={DESK - 11} r="2.2" fill={at ? '#a0aa88' : '#eef2f2'} />
              </>
            ) : (
              <Sorter mode={at ? 'work' : mode} reduce={reduce} />
            )}
            {done && !at && (
              <g transform={`translate(34 ${DESK + 18})`}>
                <circle r="8" fill={C.brand} />
                <path d="M-3.5 0l2.5 2.5 4.5-5" fill="none" stroke="#fff" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
              </g>
            )}
            {/* files arriving on the desk of whoever is working */}
            {at && s.llm && !reduce && [0, 1, 2].map((n) => (
              <use key={n} href="#tp-sheet" width="12" height="15" x="-6" y="-7" opacity="0">
                <animateMotion dur="2.4s" begin={`${n * 0.8}s`} repeatCount="indefinite"
                  path={`M${(i ? X[i - 1] - X[i] : -100) + 30} 150 Q${(i ? (X[i - 1] - X[i]) / 2 : -50)} 70 -24 ${DESK - 8}`} />
                <animate attributeName="opacity" values="0;1;1;0" keyTimes="0;.1;.85;1" dur="2.4s" begin={`${n * 0.8}s`} repeatCount="indefinite" />
              </use>
            ))}
          </g>
        )
      })}

      {/* the turn passes: one file flies from the desk that finished to the next one */}
      {handoff && !reduce && (
        <use key={handoff.id} href="#tp-sheet" width="18" height="23" x="-9" y="-11">
          <animateMotion dur="1.1s" fill="freeze" calcMode="spline" keySplines="0.4 0 0.2 1" keyTimes="0;1"
            path={`M${X[handoff.from] + 20} 150 Q${(X[handoff.from] + X[handoff.to]) / 2} 30 ${X[handoff.to] - 24} ${DESK - 8}`} />
          <animate attributeName="opacity" values="1;1;0" keyTimes="0;.85;1" dur="1.1s" fill="freeze" />
        </use>
      )}
    </svg>
  )
}

/** Speech bubble above the person at work, positioned over the scene in percent. */
export function Bubble({ index, text }: { index: number; text: string }) {
  const left = (X[index] / W) * 100
  return (
    <div className="pointer-events-none absolute top-1 z-10 -translate-x-1/2" style={{ left: `${Math.min(Math.max(left, 13), 87)}%` }}>
      <div className="tp-bubble relative max-w-56 rounded-xl border border-brand/25 bg-sheet px-3 py-1.5 text-center text-xs leading-snug text-ink shadow-sm">
        {text}
        <span className="tp-dots" aria-hidden><i>.</i><i>.</i><i>.</i></span>
        <span className="absolute -bottom-1.5 left-1/2 h-3 w-3 -translate-x-1/2 rotate-45 border-b border-r border-brand/25 bg-sheet" />
      </div>
    </div>
  )
}

/** Detects when the turn passes from one stage to the next, for the hand-over animation. */
export function useHandoff(busyKeys: Set<string>, stages: Stage[]) {
  const [handoff, setHandoff] = useState<{ from: number; to: number; id: number } | null>(null)
  const last = useRef<number | null>(null)
  const sig = [...busyKeys].sort().join(',')
  useEffect(() => {
    const idx = stages.findIndex((s) => s.llm && busyKeys.has(s.key))
    if (idx >= 0 && last.current !== null && last.current !== idx) {
      setHandoff({ from: last.current, to: idx, id: Date.now() })
    }
    if (idx >= 0) last.current = idx
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sig])
  return handoff
}
