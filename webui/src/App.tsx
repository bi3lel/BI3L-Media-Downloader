import { useEffect, useRef, useState } from "react"

type Settings = {
  output_dir: string
  media_format: string
  video_quality: string
  audio_quality: string
  also_audio: boolean
  video_no_audio: boolean
  language: string
}

type Entry = { index: number; title: string; duration?: number }

type Item = {
  id: number
  title: string
  platform: string
  thumbnail: string
  duration?: number
  drive: boolean
  entries: Entry[]
  selected: number[]
}

type Choice = {
  id: string
  track: { title: string; artists: string }
  candidates: {
    title: string
    channel?: string
    uploader?: string
    duration?: number
  }[]
}

type State = {
  phase: string
  status: string
  progress: number
  busy: boolean
  items: Item[]
  generation: number
  settings: Settings
  choice: Choice | null
  engineStatus: string
  updating: boolean
  activeTitle: string
  native: boolean
  maximized: boolean
}

const token =
  location.hash.slice(1) || sessionStorage.getItem("bi3l-session") || ""

sessionStorage.setItem("bi3l-session", token)

history.replaceState(null, "", location.pathname)

async function api(action = "state", data?: unknown): Promise<State> {
  const response = await fetch(`/api/${action}`, {
    method: data === undefined ? "GET" : "POST",
    headers: { "X-BI3L-Token": token, "Content-Type": "application/json" },
    body: data === undefined ? undefined : JSON.stringify(data),
  })

  const result = await response.json()

  if (!response.ok) throw new Error(result.error || "Request failed")

  return result
}

function Icon({
  name,
}: {
  name: "link" | "arrow" | "download" | "folder" | "settings" | "close" | "check" | "minimize" | "maximize" | "restore"
}) {
  const paths = {
    link: "M10 13a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-2 2M14 11a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l2-2",
    arrow: "M5 12h14m-5-5 5 5-5 5",
    download: "M12 3v12m-4-4 4 4 4-4M5 21h14",
    folder: "M3 7h7l2-2h9v14H3Z",
    settings:
      "M9.5 2.5h5l.5 2.4 2 1.2 2.4-.8 2.5 4.4-1.9 1.6v2.4l1.9 1.6-2.5 4.4-2.4-.8-2 1.2-.5 2.4h-5L9 20.1l-2-1.2-2.4.8-2.5-4.4L4 13.7v-2.4L2.1 9.7l2.5-4.4 2.4.8 2-1.2Z M15.5 12a3.5 3.5 0 1 1-7 0 3.5 3.5 0 0 1 7 0",
    close: "m6 6 12 12M18 6 6 18",
    check: "m5 12 4 4L19 6",
    minimize: "M5 12h14",
    maximize: "M5 5h14v14H5Z",
    restore: "M8 8h11v11H8ZM5 16V5h11",
  }

  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d={paths[name]} />
    </svg>
  )
}

function Segments({
  label,
  values,
  value,
  change,
}: {
  label: string
  values: string[]
  value: string
  change: (v: string) => void
}) {
  return (
    <div className="setting-group">
      <label>{label}</label>
      <div className="segmented" role="group" aria-label={label}>
        {values.map((v) => (
          <button
            key={v}
            className={`segment ${v === value ? "selected" : ""}`}
            aria-pressed={v === value}
            onClick={() => change(v)}
          >
            {v}
          </button>
        ))}
      </div>
    </div>
  )
}

function Toggle({
  label,
  value,
  change,
}: {
  label: string
  value: boolean
  change: (v: boolean) => void
}) {
  return (
    <div className="toggle-setting">
      <strong>{label}</strong>
      <label className="toggle">
        <input
          aria-label={label}
          type="checkbox"
          checked={value}
          onChange={(e) => change(e.target.checked)}
        />
        <span />
      </label>
    </div>
  )
}

function duration(value?: number) {
  return value
    ? `${Math.floor(value / 60)}:${String(Math.floor(value % 60)).padStart(2, "0")}`
    : ""
}

export default function App() {
  const [state, setState] = useState<State | null>(null)

  const [settings, setSettings] = useState<Settings | null>(null)

  const [urls, setUrls] = useState("")

  const [error, setError] = useState("")

  const [pending, setPending] = useState(false)

  const [modal, setModal] = useState(false)

  const [selected, setSelected] = useState<Record<string, number[]>>({})

  const [focus, setFocus] = useState(0)

  const generation = useRef(-1)

  const seeded = useRef(false)

  const pt = settings?.language === "pt-BR"

  const t = (en: string, br: string) => (pt ? br : en)

  useEffect(() => {
    let alive = true

    let timer: ReturnType<typeof setTimeout>

    async function poll() {
      try {
        const next = await api()

        if (!alive) return

        setState(next)

        if (!seeded.current) {
          setSettings(next.settings)
          seeded.current = true
        }

        if (
          generation.current !== next.generation &&
          next.phase !== "analyzing"
        ) {
          setSelected(
            Object.fromEntries(
              next.items.map((i) => [String(i.id), i.selected]),
            ),
          )

          setFocus(0)

          generation.current = next.generation
        }
      } catch (e) {
        if (alive) setError(String(e))
      }

      if (alive) timer = setTimeout(poll, 500)
    }

    void poll()

    return () => {
      alive = false
      clearTimeout(timer)
    }
  }, [])

  useEffect(() => {
    document.documentElement.lang = pt ? "pt-BR" : "en"
  }, [pt])

  useEffect(() => {
    if (!modal && !state?.choice) return

    const previous = document.activeElement as HTMLElement | null

    const dialog = document.querySelector<HTMLElement>('[role="dialog"]')

    const focusable = () =>
      Array.from(
        dialog?.querySelectorAll<HTMLElement>(
          'button:not(:disabled), input:not(:disabled), select:not(:disabled), [tabindex="0"]',
        ) || [],
      )

    focusable()[0]?.focus()

    const trap = (event: KeyboardEvent) => {
      if (event.key !== "Tab") return

      const elements = focusable()

      const first = elements[0],
        last = elements[elements.length - 1]

      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last?.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first?.focus()
      }
    }

    document.addEventListener("keydown", trap)

    return () => {
      document.removeEventListener("keydown", trap)
      previous?.focus()
    }
  }, [modal, state?.choice?.id])

  async function run(action: string, data: unknown = {}) {
    setPending(true)
    setError("")

    try {
      const next = await api(action, data)
      setState(next)
      return next
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      return null
    } finally {
      setPending(false)
    }
  }

  function change<K extends keyof Settings>(key: K, value: Settings[K]) {
    setSettings((s) => s && { ...s, [key]: value })
  }

  if (!state || !settings)
    return (
      <main className="desktop">
        <div className="connecting">
          <img className="brand-logo" src="/bi3l-logo.png" alt="BI3L" />
          <p>{error || "Connecting to BI3L…"}</p>
        </div>
      </main>
    )

  const busy = state.busy || pending || state.updating

  const item = state.items[focus]

  const selectedItems = state.items.filter(
    (i) =>
      String(i.id) in selected &&
      (!i.entries.length || selected[String(i.id)].length),
  )

  const onlyDrive =
    selectedItems.length > 0 && selectedItems.every((i) => i.drive)

  const onlySpotify =
    selectedItems.length > 0 &&
    selectedItems.every((i) => i.platform === "Spotify")

  const format = onlySpotify ? "MP3" : settings.media_format

  const progressView = state.phase === "downloading"

  const ready =
    state.items.length > 0 &&
    !progressView &&
    state.phase !== "complete" &&
    state.phase !== "analyzing"

  const toggleEntry = (index: number) =>
    setSelected((s) => {
      const values = s[String(item.id)] || []
      return {
        ...s,
        [item.id]: values.includes(index)
          ? values.filter((n) => n !== index)
          : [...values, index],
      }
    })

  return (
    <main className={`desktop ${state.native ? "native-desktop" : ""}`}>
      <section className="window" aria-label="BI3L Media Downloader">
        {!state.native && <header className="titlebar">
          <div className="header-drag"><img className="header-logo" src="/bi3l-logo.png" alt="BI3L logo"/>
            <div className="app-identity"><span>BI3L</span><span className="identity-detail">Media Downloader</span></div>
          </div>
        </header>}
        <div className="window-content">
          {!progressView && state.phase !== "complete" && (
            <form
              className="url-section"
              onSubmit={(e) => {
                e.preventDefault()
                void run("analyze", { urls })
              }}
            >
              <div className="url-input">
                <Icon name="link" />
                <input
                  aria-label={t("Media links", "Links de mídia")}
                  placeholder={t("Paste a link…", "Cole um link…")}
                  value={urls}
                  disabled={busy}
                  onChange={(e) => setUrls(e.target.value)}
                />
                {urls && (
                  <button
                    type="button"
                    aria-label={t("Clear", "Limpar")}
                    disabled={busy}
                    onClick={() => setUrls("")}
                  >
                    <Icon name="close" />
                  </button>
                )}
              </div>
              <button
                className="accent-button continue"
                disabled={busy || !urls.trim()}
              >
                {state.phase === "analyzing" ? (
                  <span className="spinner" />
                ) : (
                  <>
                    {t("Continue", "Continuar")}
                    <Icon name="arrow" />
                  </>
                )}
              </button>
            </form>
          )}
          {(error || state.phase === "error") && (
            <p role="alert" className="error-message">
              {error || state.status}
            </p>
          )}
          {state.phase === "analyzing" && (
            <div className="empty-state">
              <span className="spinner" />
              <p>
                {t("Reading media", "Lendo mídia")}{" "}
                {state.items[0]?.entries.length || ""}
              </p>
              <button
                className="secondary-button"
                disabled={pending}
                onClick={() => run("cancel")}
              >
                {t("Cancel", "Cancelar")}
              </button>
            </div>
          )}
          {state.phase === "idle" && (
            <div className="empty-state">
              <img className="brand-logo" src="/bi3l-logo.png" alt="BI3L" />
              <h1>
                {t(
                  "Paste any link to get started",
                  "Cole um link para começar",
                )}
              </h1>
            </div>
          )}
          {ready && (
            <>
              {state.items.length > 1 && (
                <div className="queue-tabs">
                  {state.items.map((i, n) => (
                    <div
                      key={i.id}
                      className={focus === n ? "queue-tab active" : "queue-tab"}
                    >
                      <input
                        type="checkbox"
                        aria-label={`${t("Include", "Incluir")} ${i.title}`}
                        checked={String(i.id) in selected}
                        onChange={(e) =>
                          setSelected((s) => {
                            const next = { ...s }
                            if (e.target.checked) next[i.id] = i.selected
                            else delete next[i.id]
                            return next
                          })
                        }
                      />
                      <button onClick={() => setFocus(n)}>{i.title}</button>
                    </div>
                  ))}
                </div>
              )}
              <div className="ready-layout">
                <section className="media-preview">
                  {item?.entries.length ? (
                    <>
                      <div className="selection-actions">
                        <strong>
                          {item.drive
                            ? t("Drive files", "Arquivos do Drive")
                            : t("Playlist", "Playlist")}
                        </strong>
                        <button
                          onClick={() =>
                            setSelected((s) => ({
                              ...s,
                              [item.id]: item.entries.map((e) => e.index),
                            }))
                          }
                        >
                          {t("Select all", "Selecionar tudo")}
                        </button>
                        <button
                          onClick={() =>
                            setSelected((s) => ({ ...s, [item.id]: [] }))
                          }
                        >
                          {t("Clear", "Limpar")}
                        </button>
                      </div>
                      <div className="entry-list">
                        {item.entries.map((e) => (
                          <label className="entry" key={e.index}>
                            <input
                              type="checkbox"
                              checked={(selected[item.id] || []).includes(
                                e.index,
                              )}
                              onChange={() => toggleEntry(e.index)}
                            />
                            <span>{e.title}</span>
                            <small>{duration(e.duration)}</small>
                          </label>
                        ))}
                      </div>
                      <p>
                        {(selected[item.id] || []).length} /{" "}
                        {item.entries.length} {t("selected", "selecionados")}
                      </p>
                    </>
                  ) : (
                    <div className="thumbnail-wrap">
                      <img
                        className={item?.thumbnail ? "" : "fallback-logo"}
                        src={item?.thumbnail || "/bi3l-logo.png"}
                        alt={item?.thumbnail ? item.title : "BI3L"}
                      />
                      {item?.duration && (
                        <span className="duration">
                          {duration(item.duration)}
                        </span>
                      )}
                    </div>
                  )}
                  <h1>{item?.title}</h1>
                  <p>{item?.platform}</p>
                </section>
                <section className="download-options">
                  {onlyDrive ? (
                    <div className="setting-group">
                      <label>{t("Format", "Formato")}</label>
                      <p className="original-format">
                        {t("Original files", "Arquivos originais")}
                      </p>
                    </div>
                  ) : (
                    <>
                      {!onlySpotify && (
                        <Segments
                          label={t("Format", "Formato")}
                          values={["MP4", "MP3"]}
                          value={format}
                          change={(v) => change("media_format", v)}
                        />
                      )}
                      {format === "MP4" && (
                        <Segments
                          label={t("Video quality", "Qualidade do vídeo")}
                          values={[
                            "Best",
                            "2160p",
                            "1440p",
                            "1080p",
                            "720p",
                            "480p",
                            "360p",
                          ]}
                          value={settings.video_quality}
                          change={(v) => change("video_quality", v)}
                        />
                      )}
                      <Segments
                        label={t("Audio quality", "Qualidade do áudio")}
                        values={[
                          "Best",
                          "320 kbps",
                          "256 kbps",
                          "192 kbps",
                          "128 kbps",
                        ]}
                        value={settings.audio_quality}
                        change={(v) => change("audio_quality", v)}
                      />
                      {format === "MP4" && (
                        <>
                          <Toggle
                            label={t(
                              "Save a separate MP3",
                              "Salvar um MP3 separado",
                            )}
                            value={settings.also_audio}
                            change={(v) => change("also_audio", v)}
                          />
                          <Toggle
                            label={t("Video without audio", "Vídeo sem áudio")}
                            value={settings.video_no_audio}
                            change={(v) => change("video_no_audio", v)}
                          />
                        </>
                      )}
                    </>
                  )}
                </section>
              </div>
            </>
          )}
          {progressView && (
            <div className="progress-view">
              <div className="file-row">
                <span className="file-icon">
                  <Icon name="download" />
                </span>
                <div className="file-info">
                  <strong>{state.activeTitle}</strong>
                  <span>{format}</span>
                </div>
                <span className="progress-number">
                  {Math.round(state.progress * 100)}%
                </span>
              </div>
              <div
                className="progress-track"
                role="progressbar"
                aria-label={t("Download progress", "Progresso")}
                aria-valuenow={Math.round(state.progress * 100)}
                aria-valuemin={0}
                aria-valuemax={100}
              >
                <span style={{ width: `${state.progress * 100}%` }} />
              </div>
              <div className="progress-meta" role="status">
                {state.status}
              </div>
              <button
                className="secondary-button cancel-button"
                disabled={pending}
                onClick={() => run("cancel")}
              >
                {t("Cancel download", "Cancelar download")}
              </button>
            </div>
          )}
          {state.phase === "complete" && (
            <div className="complete-view">
              <span className="success-icon">
                <Icon name="check" />
              </span>
              <div>
                <h1>{t("Download complete", "Download concluído")}</h1>
                <p>{state.status}</p>
              </div>
              <div className="complete-actions">
                <button
                  className="secondary-button"
                  onClick={() => run("open-folder")}
                >
                  <Icon name="folder" />
                  {t("Show folder", "Abrir pasta")}
                </button>
                <button
                  className="accent-button"
                  disabled={busy}
                  onClick={() => {
                    setUrls("")
                    void run("reset")
                  }}
                >
                  {t("New download", "Novo download")}
                </button>
              </div>
            </div>
          )}
          {state.phase === "cancelled" && (
            <p className="notice" role="status">
              {t(
                "Cancelled. You can change your selection and try again.",
                "Cancelado. Você pode alterar a seleção e tentar novamente.",
              )}
            </p>
          )}
        </div>
        <footer className="actionbar">
          <button
            className="settings-button"
            onClick={() => setModal(true)}
            aria-label={t("Settings", "Configurações")}
            title={t("Settings", "Configurações")}
          >
            <Icon name="settings" />
          </button>
          {state.phase === "complete" ? (
            <span className="saved-status">
              <Icon name="check" />
              {t("Saved", "Salvo")}
            </span>
          ) : (
            <button
              className="accent-button download-button"
              disabled={!ready || busy || !selectedItems.length}
              onClick={() =>
                run("download", {
                  generation: state.generation,
                  selected,
                  settings: { ...settings, media_format: format },
                })
              }
            >
              <Icon name="download" />
              {t("Download", "Baixar")}
            </button>
          )}
        </footer>
        {modal && (
          <div className="modal-backdrop" onClick={() => setModal(false)}>
            <section
              className="settings-modal"
              role="dialog"
              aria-modal="true"
              aria-label={t("Settings", "Configurações")}
              onClick={(e) => e.stopPropagation()}
              onKeyDown={(e) => {
                if (e.key === "Escape") setModal(false)
              }}
            >
              <header>
                <h2>{t("Settings", "Configurações")}</h2>
                <button
                  className="toolbar-button"
                  autoFocus
                  aria-label={t("Close", "Fechar")}
                  onClick={() => setModal(false)}
                >
                  <Icon name="close" />
                </button>
              </header>
              <div className="settings-row folder-setting">
                <label htmlFor="destination">
                  {t("Save folder", "Pasta de destino")}
                </label>
                <div className="folder-picker">
                  <input
                    id="destination"
                    disabled={busy}
                    value={settings.output_dir}
                    onChange={(e) => change("output_dir", e.target.value)}
                  />
                  <button
                    className="secondary-button"
                    disabled={busy}
                    onClick={async () => {
                      const next = await run("browse")
                      if (next) change("output_dir", next.settings.output_dir)
                    }}
                  >
                    {t("Browse…", "Procurar…")}
                  </button>
                </div>
              </div>
              <div className="settings-row">
                <strong>{t("Language", "Idioma")}</strong>
                <select
                  aria-label={t("Language", "Idioma")}
                  className="select-button"
                  disabled={busy}
                  value={settings.language}
                  onChange={(e) => change("language", e.target.value)}
                >
                  <option value="en">English</option>
                  <option value="pt-BR">Português (Brasil)</option>
                </select>
              </div>
              <div className="settings-row">
                <span>
                  <strong>{t("Download engine", "Motor de download")}</strong>
                  <small>{state.engineStatus || "yt-dlp"}</small>
                </span>
                <button
                  className="secondary-button"
                  disabled={busy}
                  onClick={() => run("update-engine")}
                >
                  {state.updating ? "…" : t("Update", "Atualizar")}
                </button>
              </div>
              {error && (
                <p className="error-message" role="alert">
                  {error}
                </p>
              )}
              <footer>
                <button
                  className="accent-button"
                  disabled={busy}
                  onClick={async () => {
                    if (await run("settings", settings)) setModal(false)
                  }}
                >
                  {t("Save", "Salvar")}
                </button>
              </footer>
            </section>
          </div>
        )}
        {state.choice && (
          <div className="modal-backdrop">
            <section
              className="settings-modal choice-modal"
              role="dialog"
              aria-modal="true"
              aria-label={t(
                "Choose the matching song",
                "Escolha a música correta",
              )}
            >
              <header>
                <div>
                  <h2>
                    {t("Choose the matching song", "Escolha a música correta")}
                  </h2>
                  <p>
                    {state.choice.track.title} — {state.choice.track.artists}
                  </p>
                </div>
              </header>
              <div className="candidate-list">
                {state.choice.candidates.map((candidate, index) => (
                  <button
                    className="candidate"
                    key={index}
                    disabled={pending}
                    onClick={() =>
                      run("choose", { id: state.choice?.id, index })
                    }
                  >
                    <strong>{candidate.title}</strong>
                    <small>
                      {candidate.channel || candidate.uploader} ·{" "}
                      {duration(candidate.duration)}
                    </small>
                  </button>
                ))}
              </div>
              <footer>
                <button
                  className="secondary-button"
                  onClick={() =>
                    run("choose", { id: state.choice?.id, index: null })
                  }
                >
                  {t("Skip this song", "Pular esta música")}
                </button>
              </footer>
            </section>
          </div>
        )}
      </section>
    </main>
  )
}
