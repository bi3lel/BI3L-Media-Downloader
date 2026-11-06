import { useState } from "react"

export type Clip = [number, number]
type Translate = (en: string, pt: string) => string

function timecode(seconds: number) {
  const ms = Math.round(seconds * 1000)
  const whole = Math.floor(ms / 1000)
  const fraction = String(ms % 1000).padStart(3, "0").replace(/0+$/, "")
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, "0")}${fraction ? "." + fraction : ""}`
}

function parseTime(text: string) {
  const parts = text.trim().split(":")
  if (parts.length > 3 || parts.some((part, i) =>
    !(i === parts.length - 1 ? /^\d+(\.\d{1,3})?$/ : /^\d+$/).test(part)
    || (i > 0 && Number(part) >= 60)
  )) return NaN
  return parts.reduce((time, part) => time * 60 + Number(part), 0)
}

function TimeField({ label, value, commit }: {
  label: string
  value: number
  commit: (value: number) => void
}) {
  const [draft, setDraft] = useState<string | null>(null)
  return (
    <label>
      {label}
      <input
        type="text"
        spellCheck={false}
        value={draft ?? timecode(value)}
        onChange={(e) => setDraft(e.currentTarget.value)}
        onBlur={() => {
          if (draft !== null) commit(parseTime(draft))
          setDraft(null)
        }}
        onKeyDown={(e) => { if (e.key === "Enter") e.currentTarget.blur() }}
      />
    </label>
  )
}

export default function ClipRange({ duration, clip, change, invalid, setInvalid, t }: {
  duration: number
  clip?: Clip
  change: (clip?: Clip) => void
  invalid: boolean
  setInvalid: (invalid: boolean) => void
  t: Translate
}) {
  const [start, end] = clip ?? [0, duration]
  const labels = [t("Start", "Início"), t("End", "Fim")]
  const round = (seconds: number) => Math.round(seconds * 1000) / 1000
  const min = [0, round(start + 1)]
  const max = [round(end - 1), duration]
  const update = (i: number, value: number) => {
    if (!Number.isFinite(value) || value < min[i] || value > max[i]) {
      setInvalid(true)
      return
    }
    setInvalid(false)
    change(i === 0 ? [value, end] : [start, value])
  }
  const move = (i: number, value: number) =>
    update(i, Math.max(min[i], Math.min(max[i], value)))

  return (
    <section className="clip-range">
      <label className="clip-toggle">
        <input type="checkbox" checked={!!clip} onChange={(e) => {
          setInvalid(false)
          change(e.currentTarget.checked ? [0, duration] : undefined)
        }} />
        {t("Download a clip", "Baixar um trecho")}
      </label>
      {clip && <>
        <div className="clip-slider">
          <div className="clip-track" aria-hidden="true">
            <span style={{ left: `${start / duration * 100}%`, right: `${(1 - end / duration) * 100}%` }} />
          </div>
          {clip.map((value, i) => (
            <input key={i} type="range" min={0} max={duration} step="any"
              value={value} aria-label={labels[i]} aria-valuetext={timecode(value)}
              onChange={(e) => {
                const next = e.currentTarget.valueAsNumber
                move(i, next >= duration - 0.5 ? duration : Math.round(next))
              }}
              onKeyDown={(e) => {
                const offset = { ArrowLeft: -1, ArrowDown: -1, ArrowRight: 1, ArrowUp: 1, PageDown: -10, PageUp: 10 }[e.key]
                if (offset === undefined && e.key !== "Home" && e.key !== "End") return
                e.preventDefault()
                move(i, e.key === "Home" ? min[i] : e.key === "End" ? max[i] : round(value + (offset ?? 0)))
              }}
            />
          ))}
        </div>
        <div className="clip-times">
          <TimeField label={labels[0]} value={start} commit={(value) => update(0, value)} />
          <TimeField label={labels[1]} value={end} commit={(value) => update(1, value)} />
          <output>{t("Length", "Duração")} <strong>{timecode(end - start)}</strong></output>
        </div>
        {invalid && <p className="clip-error" role="alert">
          {t("Use mm:ss and leave at least one second between start and end.", "Use mm:ss e deixe pelo menos um segundo entre o início e o fim.")}
        </p>}
      </>}
    </section>
  )
}
