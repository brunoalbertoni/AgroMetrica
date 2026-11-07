import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { COR_SISTEMA, SISTEMA, data, numero } from '../../compartilhado/format'
import GraficoCombinado from '../../compartilhado/graficos/GraficoCombinado'
import LinhasChart from '../../compartilhado/graficos/LinhasChart'
import { SeverityBadge } from '../../compartilhado/ui'
import BBoxCanvas from '../diagnosticos/BBoxCanvas'

/** Número que sobe de 0 até o valor, para o indicador "chegar" na tela. */
function Contador({ valor, casas = 0, unidade = '' }) {
  const [atual, setAtual] = useState(0)
  useEffect(() => {
    if (valor === null || valor === undefined) return undefined
    const inicio = performance.now()
    let quadro
    const passo = (agora) => {
      const t = Math.min((agora - inicio) / 800, 1)
      setAtual(valor * (1 - Math.pow(1 - t, 3)))
      if (t < 1) quadro = requestAnimationFrame(passo)
    }
    quadro = requestAnimationFrame(passo)
    return () => cancelAnimationFrame(quadro)
  }, [valor])
  if (valor === null || valor === undefined) return <span className="text-muted">—</span>
  return (
    <span className="tabular">
      {numero(atual, casas)}
      {unidade}
    </span>
  )
}

const corDaSerie = (s) => s.cor ?? COR_SISTEMA[s.sistema]

function seriesParaGrafico(series) {
  return series.map((s) => ({ ...s, cor: corDaSerie(s) }))
}

function Grafico({ painel }) {
  return (
    <div className="painel-item">
      <LinhasChart
        series={seriesParaGrafico(painel.series)}
        dominio={painel.dominio}
        casas={painel.casas}
        unidade={painel.unidade}
        altura={380}
        animado
      />
      {painel.series.some((s) => s.sistema) && (
        <p className="mt-2 text-xs text-muted">Linha contínua: grão. Tracejada: silagem.</p>
      )}
    </div>
  )
}

function Comparativo({ painel }) {
  const [a, b] = painel.talhoes
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-3">
        {[a, b].map((t, i) => (
          <div
            key={t.id}
            className="painel-item rounded-md border border-line p-3"
            style={{ '--atraso': `${i * 80}ms` }}
          >
            <p className="font-display text-lg font-semibold">{t.nome}</p>
            <p className="text-sm text-muted" style={{ color: COR_SISTEMA[t.sistema] }}>
              {SISTEMA[t.sistema]}
            </p>
          </div>
        ))}
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        {painel.indicadores.map((ind, i) => {
          const casas = ind.rotulo.includes('NDVI') ? 2 : 0
          return (
            <div
              key={ind.rotulo}
              className="painel-item rounded-md border border-line p-3"
              style={{ '--atraso': `${160 + i * 90}ms` }}
            >
              <p className="mb-2 text-sm text-muted">{ind.rotulo}</p>
              <div className="grid grid-cols-2 gap-2">
                {['a', 'b'].map((lado) => (
                  <div
                    key={lado}
                    className={`rounded px-2 py-1.5 ${
                      ind.melhor === lado ? 'bg-canopy-soft ring-1 ring-canopy/40' : ''
                    }`}
                  >
                    <p className="font-display text-2xl font-semibold">
                      <Contador valor={ind[lado]} casas={casas} unidade={ind.unidade} />
                    </p>
                    {ind.melhor === lado && <p className="text-xs font-medium text-canopy">▲ melhor</p>}
                    {ind.sem_dados?.includes(lado) && (
                      <p className="text-xs text-muted">sem leituras de armadilha</p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )
        })}
      </div>

      <div className="painel-item" style={{ '--atraso': '500ms' }}>
        <p className="mb-1 text-sm font-medium">NDVI ao longo da safra</p>
        <LinhasChart series={seriesParaGrafico(painel.series)} dominio={[0, 1]} altura={280} animado />
      </div>
    </div>
  )
}

function Galeria({ painel }) {
  return (
    <div className={`grid gap-4 ${painel.itens.length > 1 ? 'sm:grid-cols-2' : ''}`}>
      {painel.itens.map((item, i) => (
        <article
          key={item.diagnostico_id}
          className="painel-item rounded-md border border-line p-3"
          style={{ '--atraso': `${i * 120}ms` }}
        >
          <div className="mb-2 flex items-center gap-2">
            <SeverityBadge severidade={item.severidade} />
            <p className="min-w-0 truncate text-sm font-medium">{item.praga}</p>
            <span className="ml-auto whitespace-nowrap text-sm text-muted tabular">
              {item.contagem} detecções
            </span>
          </div>
          <BBoxCanvas src={item.imagem_url} caixas={item.bboxes} alt={item.titulo} animar />
          <div className="mt-2 flex items-center justify-between text-xs text-muted">
            <span>
              {item.talhao} · {data(item.data)}
            </span>
            <Link to={`/diagnosticos/${item.diagnostico_id}`} className="text-canopy hover:underline">
              Abrir diagnóstico
            </Link>
          </div>
        </article>
      ))}
    </div>
  )
}

function Combinado({ painel }) {
  return (
    <div className="painel-item">
      <GraficoCombinado painel={painel} />
    </div>
  )
}

const TIPOS = {
  grafico_linhas: Grafico,
  grafico_combinado: Combinado,
  comparativo: Comparativo,
  galeria_pragas: Galeria,
}

/**
 * Painel que cobre o conteúdo da página, à esquerda do chat, e desenha o que o assistente pediu
 * (gráfico, comparativo, fotos de pragas). O formato vem da API (tipos de uma lista fixa).
 */
export default function PainelVisual({ paineis, indice, onTrocar, onFechar }) {
  const painel = paineis[indice]
  const Conteudo = TIPOS[painel?.tipo]
  if (!Conteudo) return null
  return (
    <section
      aria-label="Visualização do assistente"
      className="painel-entra fixed bottom-4 left-0 right-4 top-4 z-[60] flex flex-col overflow-hidden rounded-r-xl border border-l-0 border-line bg-panel shadow-2xl min-[1100px]:right-[calc(440px+1rem)] min-[1100px]:z-50"
    >
      <header className="flex items-center gap-3 border-b border-line px-5 py-3">
        <h2 className="min-w-0 flex-1 truncate text-lg font-semibold">{painel.titulo}</h2>
        {paineis.length > 1 && (
          <div className="flex items-center gap-1 text-sm text-muted">
            <button
              type="button"
              onClick={() => onTrocar(indice - 1)}
              disabled={indice === 0}
              aria-label="Painel anterior"
              className="rounded px-2 py-1 hover:bg-paper disabled:opacity-30"
            >
              ‹
            </button>
            <span className="tabular">
              {indice + 1}/{paineis.length}
            </span>
            <button
              type="button"
              onClick={() => onTrocar(indice + 1)}
              disabled={indice === paineis.length - 1}
              aria-label="Próximo painel"
              className="rounded px-2 py-1 hover:bg-paper disabled:opacity-30"
            >
              ›
            </button>
          </div>
        )}
        <button
          type="button"
          onClick={onFechar}
          aria-label="Fechar visualização"
          className="rounded p-1.5 text-muted hover:bg-paper hover:text-ink"
        >
          <svg viewBox="0 0 24 24" className="h-6 w-6" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M6 6l12 12M18 6L6 18" strokeLinecap="round" />
          </svg>
        </button>
      </header>
      <div key={indice} className="flex-1 overflow-y-auto p-5">
        <Conteudo painel={painel} />
      </div>
    </section>
  )
}
