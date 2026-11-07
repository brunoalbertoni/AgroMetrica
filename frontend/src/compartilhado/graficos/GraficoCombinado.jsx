import { useCallback, useMemo, useState } from 'react'
import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { COR_SISTEMA, data as fmtData, dataCurta, numero } from '../format'

const EIXO = { stroke: 'var(--color-muted)', fill: 'var(--color-muted)', fontSize: 12 }

/** Cor de cada tipo de anotação (a caixa usa o contorno; o fundo é o do tema). */
const COR_NOTA = {
  chuva: '#3a63a8',
  ndvi: 'var(--color-serie-40)',
  queda: 'var(--color-alarm)',
  praga: '#c2362b',
  manejo: '#b8860b',
  ia: 'var(--color-canopy)',
}
const ALTURA_CAIXA = 20
const PASSO_CAIXA = ALTURA_CAIXA + 4
const MAX_NIVEIS = 7
const ESPACO_ENTRE_CAIXAS = 6
const LARGURA_EIXO_ESQ = 48
const LARGURA_EIXO_DIR = 44

const corDaSerie = (s) => s.cor ?? COR_SISTEMA[s.sistema]

function truncar(texto, limite) {
  return texto.length > limite ? `${texto.slice(0, limite - 1)}…` : texto
}

const textoDaCaixa = (nota) => `${nota.id}. ${truncar(nota.rotulo, 30)}`
const larguraDaCaixa = (nota) => Math.min(textoDaCaixa(nota).length * 5.9 + 16, 230)

/** Junta as séries por data e garante uma linha para a data de cada anotação (a linha vertical precisa dela). */
function mesclar(series, anotacoes) {
  const porData = new Map()
  const linha = (d) => {
    if (!porData.has(d)) porData.set(d, { data: d })
    return porData.get(d)
  }
  for (const s of series) for (const p of s.pontos) linha(String(p.data).slice(0, 10))[s.id] = p.valor
  for (const a of anotacoes) linha(a.data)
  return [...porData.values()].sort((a, b) => a.data.localeCompare(b.data))
}

/**
 * Distribui as caixas em alturas (níveis) sem que uma cubra a outra: percorre as anotações em ordem de data e
 * põe cada caixa no primeiro nível em que ela cabe ao lado da última que já está lá. Perto da borda direita,
 * a caixa se estende para a esquerda da linha.
 */
function posicionarCaixas(anotacoes, datas, larguraPlot, margemEsq) {
  const ultimoFim = Array(MAX_NIVEIS).fill(-Infinity)
  return anotacoes.map((nota) => {
    const x = margemEsq + ((datas.indexOf(nota.data) + 0.5) / datas.length) * larguraPlot
    const largura = larguraDaCaixa(nota)
    const lado = x + largura > margemEsq + larguraPlot ? 'esquerda' : 'direita'
    const inicio = lado === 'esquerda' ? x - largura : x
    let nivel = ultimoFim.findIndex((fim) => inicio >= fim + ESPACO_ENTRE_CAIXAS)
    if (nivel === -1) nivel = ultimoFim.indexOf(Math.min(...ultimoFim)) // lotado: usa o que liberta primeiro
    ultimoFim[nivel] = inicio + largura
    return { nivel, lado }
  })
}

/** Caixa de texto presa à linha vertical da anotação. */
function CaixaNota({ viewBox, nota, nivel, lado, atraso }) {
  if (!viewBox) return null
  const largura = larguraDaCaixa(nota)
  const x = lado === 'esquerda' ? viewBox.x - largura : viewBox.x
  const y = viewBox.y + 4 + nivel * PASSO_CAIXA
  const cor = COR_NOTA[nota.tipo] ?? 'var(--color-muted)'
  return (
    <g className="painel-nota" style={{ '--atraso': `${atraso}ms` }}>
      <rect
        x={x}
        y={y}
        width={largura}
        height={ALTURA_CAIXA}
        rx={4}
        fill="var(--color-panel)"
        stroke={cor}
        strokeWidth={1.5}
      />
      <text x={x + 7} y={y + 14} fontSize={11} fontWeight={600} fill="var(--color-ink)">
        {textoDaCaixa(nota)}
      </text>
    </g>
  )
}

function Dica({ active, payload, label, series }) {
  if (!active || !payload?.length) return null
  const porId = Object.fromEntries(series.map((s) => [s.id, s]))
  return (
    <div className="rounded border border-line bg-panel px-3 py-2 text-xs shadow-md">
      <p className="mb-1 font-medium text-ink">{fmtData(label)}</p>
      {payload
        .filter((p) => p.value !== null && p.value !== undefined)
        .map((p) => {
          const s = porId[p.dataKey]
          return (
            <p key={p.dataKey} className="flex items-center gap-2 text-ink">
              <span
                className="inline-block h-0.5 w-3"
                style={{ background: p.color ?? p.fill }}
                aria-hidden
              />
              <span className="text-muted">{p.name}</span>
              <span className="ml-auto pl-3 font-medium tabular">
                {numero(p.value, s?.casas ?? 2)}
                {s?.unidade ?? ''}
              </span>
            </p>
          )
        })}
    </div>
  )
}

/** Eixo esquerdo com folga no alto para as caixas de anotação (os ticks continuam só até o valor real). */
function eixoEsquerdo(eixo, temAnotacoes) {
  const [min, max] = eixo.dominio
  if (typeof min === 'number' && typeof max === 'number') {
    const folga = temAnotacoes ? (max - min) * 0.55 : 0
    const passo = (max - min) / 4
    return { dominio: [min, max + folga], ticks: [0, 1, 2, 3, 4].map((i) => min + i * passo) }
  }
  return {
    dominio: [min, temAnotacoes ? (dataMax) => dataMax + Math.abs(dataMax) * 0.55 : max],
    ticks: undefined,
  }
}

/**
 * Gráfico de linhas e barras com dois eixos e anotações em caixas de texto.
 * painel: { eixos: {esq, dir?}, series: [{id, nome, tipo: 'linha'|'barra', eixo, cor?|sistema?, pontos}],
 *           anotacoes: [{id, data, rotulo, tipo}] }
 */
export default function GraficoCombinado({ painel, altura = 420 }) {
  const { eixos, series, anotacoes = [] } = painel
  const [largura, setLargura] = useState(700)
  // mede a largura do gráfico para saber onde cada caixa cai e distribuí-las sem sobreposição
  const medir = useCallback((no) => {
    if (!no) return undefined
    const observador = new ResizeObserver(([entrada]) => setLargura(entrada.contentRect.width))
    observador.observe(no)
    return () => observador.disconnect()
  }, [])

  const linhas = useMemo(() => mesclar(series, anotacoes), [series, anotacoes])
  const datas = useMemo(() => linhas.map((l) => l.data), [linhas])
  const eixoDireito = eixos.dir
  const margemDir = eixoDireito ? LARGURA_EIXO_DIR + 4 : 16
  const posicoes = useMemo(
    () => posicionarCaixas(anotacoes, datas, largura - LARGURA_EIXO_ESQ - margemDir, LARGURA_EIXO_ESQ),
    [anotacoes, datas, largura, margemDir],
  )

  // as unidades de cada série vêm do eixo a que pertencem (para o tooltip)
  const comUnidade = series.map((s) => ({
    ...s,
    casas: eixos[s.eixo]?.casas,
    unidade: eixos[s.eixo]?.unidade,
  }))
  const esquerdo = eixoEsquerdo(eixos.esq, anotacoes.length > 0)
  const barras = series.filter((s) => s.tipo === 'barra')
  const dominioDireito = barras.length ? [0, (max) => Math.ceil(max * 3)] : ['auto', 'auto'] // barras só na faixa de baixo

  return (
    <div>
      <div ref={medir} style={{ height: altura }}>
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={linhas} margin={{ top: 8, right: eixoDireito ? 4 : 16, left: 0, bottom: 0 }}>
            <CartesianGrid stroke="var(--color-line)" strokeOpacity={0.6} vertical={false} />
            <XAxis
              dataKey="data"
              tickFormatter={dataCurta}
              tick={EIXO}
              tickLine={false}
              axisLine={{ stroke: 'var(--color-line)' }}
              minTickGap={28}
            />
            <YAxis
              yAxisId="esq"
              domain={esquerdo.dominio}
              ticks={esquerdo.ticks}
              tick={EIXO}
              tickLine={false}
              axisLine={false}
              width={LARGURA_EIXO_ESQ}
              tickFormatter={(v) => numero(v, eixos.esq.casas > 1 ? 1 : eixos.esq.casas)}
            />
            {eixoDireito && (
              <YAxis
                yAxisId="dir"
                orientation="right"
                domain={dominioDireito}
                tick={EIXO}
                tickLine={false}
                axisLine={false}
                width={LARGURA_EIXO_DIR}
                tickFormatter={(v) => numero(v, 0)}
              />
            )}
            <Tooltip
              content={<Dica series={comUnidade} />}
              cursor={{ stroke: 'var(--color-muted)', strokeDasharray: '3 3' }}
            />
            <Legend
              verticalAlign="top"
              height={28}
              iconType="plainline"
              wrapperStyle={{ fontSize: 12, color: 'var(--color-ink)' }}
            />
            {barras.map((s) => (
              <Bar
                key={s.id}
                yAxisId={s.eixo}
                dataKey={s.id}
                name={s.nome}
                fill={corDaSerie(s)}
                fillOpacity={0.45}
                maxBarSize={9}
                isAnimationActive
                animationDuration={800}
              />
            ))}
            {series
              .filter((s) => s.tipo === 'linha')
              .map((s) => (
                <Line
                  key={s.id}
                  yAxisId={s.eixo}
                  type="monotone"
                  dataKey={s.id}
                  name={s.nome}
                  stroke={corDaSerie(s)}
                  strokeWidth={2}
                  strokeDasharray={s.tracejado ? '6 4' : undefined}
                  dot={false}
                  activeDot={{ r: 4, stroke: 'var(--color-panel)', strokeWidth: 2 }}
                  connectNulls
                  isAnimationActive
                  animationDuration={900}
                />
              ))}
            {anotacoes.map((nota, i) => (
              <ReferenceLine
                key={nota.id}
                yAxisId="esq"
                x={nota.data}
                stroke={COR_NOTA[nota.tipo] ?? 'var(--color-muted)'}
                strokeDasharray="3 3"
                strokeOpacity={0.8}
                label={
                  <CaixaNota
                    nota={nota}
                    nivel={posicoes[i].nivel}
                    lado={posicoes[i].lado}
                    atraso={500 + i * 140}
                  />
                }
              />
            ))}
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {anotacoes.length > 0 && (
        <ol className="mt-3 grid gap-x-6 gap-y-1.5 text-sm sm:grid-cols-2">
          {anotacoes.map((nota, i) => (
            <li
              key={nota.id}
              className="painel-item flex items-start gap-2"
              style={{ '--atraso': `${600 + i * 90}ms` }}
            >
              <span
                className="mt-0.5 inline-flex h-5 min-w-5 items-center justify-center rounded-full px-1 text-[11px] font-semibold text-white"
                style={{ background: COR_NOTA[nota.tipo] ?? 'var(--color-muted)' }}
              >
                {nota.id}
              </span>
              <span>
                <span className="text-muted tabular">{dataCurta(nota.data)}</span> {nota.rotulo}
              </span>
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}
