import { useEffect, useRef } from 'react'

import { SEVERIDADE, SISTEMA } from '../lib/format'

export function PageHeader({ titulo, descricao, children }) {
  return (
    <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-3xl font-semibold">{titulo}</h1>
        {descricao && <p className="mt-1 max-w-2xl text-muted">{descricao}</p>}
      </div>
      {children && <div className="flex flex-wrap gap-2">{children}</div>}
    </header>
  )
}

export function Panel({ titulo, acao, children, className = '' }) {
  return (
    <section className={`rounded-md border border-line bg-panel ${className}`}>
      {titulo && (
        <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-3">
          <h2 className="text-lg font-semibold">{titulo}</h2>
          {acao}
        </div>
      )}
      <div className="p-4">{children}</div>
    </section>
  )
}

const VARIANTES = {
  primario: 'bg-canopy text-white hover:bg-canopy-dark disabled:bg-canopy/50',
  secundario:
    'border border-line bg-panel text-ink hover:border-canopy hover:text-canopy disabled:opacity-50',
  perigo: 'border border-alarm/40 bg-panel text-alarm hover:bg-alarm-soft disabled:opacity-50',
  texto: 'text-canopy hover:underline disabled:opacity-50',
}

export function Button({ variante = 'primario', className = '', type = 'button', ...props }) {
  const base = variante === 'texto' ? 'px-1' : 'rounded px-3.5 py-2'
  return (
    <button
      type={type}
      className={`${base} inline-flex items-center justify-center gap-2 text-sm font-medium transition-colors disabled:cursor-not-allowed ${VARIANTES[variante]} ${className}`}
      {...props}
    />
  )
}

export function Field({ label, erro, children, dica }) {
  return (
    <label className="block text-sm">
      <span className="mb-1 block font-medium text-ink">{label}</span>
      {children}
      {dica && !erro && <span className="mt-1 block text-xs text-muted">{dica}</span>}
      {erro && <span className="mt-1 block text-xs text-alarm">{erro}</span>}
    </label>
  )
}

export const inputClass =
  'w-full rounded border border-line bg-white px-3 py-2 text-sm text-ink placeholder:text-muted/70 focus:border-canopy focus:outline-none focus:ring-2 focus:ring-canopy/20'

export function SeverityBadge({ severidade }) {
  if (!severidade) return <span className="text-muted">—</span>
  const estilo = {
    ALTA: 'bg-alarm text-white',
    MEDIA: 'bg-straw text-ink',
    BAIXA: 'bg-line text-ink',
  }[severidade]
  return (
    <span className={`inline-block rounded-sm px-2 py-0.5 text-xs font-semibold ${estilo}`}>
      {SEVERIDADE[severidade]}
    </span>
  )
}

export function SistemaTag({ sistema }) {
  const cor = sistema === 'AGRO_4_0' ? 'border-serie-40 text-serie-40' : 'border-serie-conv text-serie-conv'
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-sm border px-1.5 py-0.5 text-xs font-medium ${cor}`}
    >
      <span
        className={`h-1.5 w-1.5 rounded-full ${sistema === 'AGRO_4_0' ? 'bg-serie-40' : 'bg-serie-conv'}`}
      />
      {SISTEMA[sistema] ?? sistema}
    </span>
  )
}

export function EmptyState({ titulo, children, acao }) {
  return (
    <div className="rounded-md border border-dashed border-line bg-panel px-6 py-10 text-center">
      <p className="font-display text-xl font-semibold">{titulo}</p>
      {children && <p className="mx-auto mt-1 max-w-md text-sm text-muted">{children}</p>}
      {acao && <div className="mt-4">{acao}</div>}
    </div>
  )
}

export function ErrorMessage({ children }) {
  if (!children) return null
  return (
    <p role="alert" className="rounded border border-alarm/30 bg-alarm-soft px-3 py-2 text-sm text-alarm">
      {children}
    </p>
  )
}

export function Loading({ texto = 'Carregando…' }) {
  return <p className="py-8 text-center text-sm text-muted">{texto}</p>
}

export function Stat({ rotulo, valor, detalhe, tom }) {
  const cor = { alarm: 'text-alarm', straw: 'text-[#9a7210]', canopy: 'text-canopy' }[tom] ?? 'text-ink'
  return (
    <div className="rounded-md border border-line bg-panel px-4 py-3">
      <p className="text-sm text-muted">{rotulo}</p>
      <p className={`font-display text-3xl font-semibold tabular ${cor}`}>{valor}</p>
      {detalhe && <p className="text-xs text-muted">{detalhe}</p>}
    </div>
  )
}

export function Modal({ aberto, titulo, onFechar, children }) {
  const ref = useRef(null)
  useEffect(() => {
    const dialogo = ref.current
    if (!dialogo) return
    if (aberto && !dialogo.open) dialogo.showModal()
    if (!aberto && dialogo.open) dialogo.close()
  }, [aberto])
  return (
    <dialog
      ref={ref}
      onClose={onFechar}
      className="m-auto w-[min(560px,calc(100vw-2rem))] rounded-md border border-line bg-panel p-0 text-ink backdrop:bg-ink/40"
    >
      <div className="flex items-center justify-between border-b border-line px-5 py-3">
        <h2 className="text-xl font-semibold">{titulo}</h2>
        <button
          type="button"
          onClick={onFechar}
          className="rounded px-2 text-2xl leading-none text-muted hover:text-ink"
          aria-label="Fechar"
        >
          ×
        </button>
      </div>
      <div className="max-h-[75vh] overflow-y-auto px-5 py-4">{aberto && children}</div>
    </dialog>
  )
}

export function Tabs({ abas, ativa, onTrocar }) {
  return (
    <div role="tablist" className="mb-5 flex gap-1 overflow-x-auto border-b border-line">
      {abas.map((aba) => (
        <button
          key={aba.id}
          role="tab"
          type="button"
          aria-selected={ativa === aba.id}
          onClick={() => onTrocar(aba.id)}
          className={`-mb-px whitespace-nowrap border-b-2 px-4 py-2 text-sm font-medium ${
            ativa === aba.id ? 'border-canopy text-canopy' : 'border-transparent text-muted hover:text-ink'
          }`}
        >
          {aba.rotulo}
        </button>
      ))}
    </div>
  )
}
