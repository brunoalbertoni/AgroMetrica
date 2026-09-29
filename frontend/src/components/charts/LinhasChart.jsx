import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { COR_SEVERIDADE, data as fmtData, dataCurta, numero } from '../../lib/format'

const EIXO = { stroke: '#5d6b62', fontSize: 12 }

/** Junta várias séries [{data, valor}] em linhas {data, [id]: valor} ordenadas por data. */
function mesclar(series) {
  const porData = new Map()
  for (const s of series) {
    for (const p of s.pontos) {
      const chave = String(p.data).slice(0, 10)
      if (!porData.has(chave)) porData.set(chave, { data: chave })
      porData.get(chave)[s.id] = p.valor
    }
  }
  return [...porData.values()].sort((a, b) => a.data.localeCompare(b.data))
}

function DicaTooltip({ active, payload, label, casas, unidade }) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded border border-line bg-panel px-3 py-2 text-xs shadow-md">
      <p className="mb-1 font-medium text-ink">{fmtData(label)}</p>
      {payload.map((p) => (
        <p key={p.dataKey} className="flex items-center gap-2 text-ink">
          <span className="inline-block h-0.5 w-3" style={{ background: p.color }} aria-hidden />
          <span className="text-muted">{p.name}</span>
          <span className="ml-auto pl-3 font-medium tabular">
            {numero(p.value, casas)}
            {unidade}
          </span>
        </p>
      ))}
    </div>
  )
}

/** Rótulo direto só no último ponto de cada série. */
function rotuloFinal(serie, total) {
  return function Rotulo({ x, y, index }) {
    if (index !== total - 1 || x === undefined) return null
    return (
      <text x={x + 6} y={y} dy={4} fontSize={11} fill="#1f2a24">
        {serie.rotuloCurto ?? serie.nome}
      </text>
    )
  }
}

/**
 * Gráfico de linhas de uma métrica (um único eixo Y).
 * series: [{ id, nome, cor, tracejado?, pontos: [{ data, valor }] }]
 * eventos: [{ data, severidade, rotulo }] viram linhas verticais.
 */
export default function LinhasChart({
  series,
  altura = 280,
  dominio = ['auto', 'auto'],
  casas = 2,
  unidade = '',
  eventos = [],
  rotulosDiretos = true,
}) {
  const linhas = mesclar(series)
  if (linhas.length === 0)
    return <p className="py-10 text-center text-sm text-muted">Sem dados no período.</p>
  const multiplas = series.length > 1

  return (
    <div style={{ height: altura }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart
          data={linhas}
          margin={{ top: 8, right: rotulosDiretos && multiplas ? 136 : 16, left: 0, bottom: 0 }}
        >
          <CartesianGrid stroke="#e7eae3" vertical={false} />
          <XAxis
            dataKey="data"
            tickFormatter={dataCurta}
            tick={EIXO}
            tickLine={false}
            axisLine={{ stroke: '#d8ddd3' }}
            minTickGap={24}
          />
          <YAxis
            domain={dominio}
            tick={EIXO}
            tickLine={false}
            axisLine={false}
            width={48}
            tickFormatter={(v) => numero(v, casas > 1 ? 1 : casas)}
          />
          <Tooltip
            content={<DicaTooltip casas={casas} unidade={unidade} />}
            cursor={{ stroke: '#5d6b62', strokeDasharray: '3 3' }}
          />
          {multiplas && (
            <Legend
              verticalAlign="top"
              height={28}
              iconType="plainline"
              wrapperStyle={{ fontSize: 12, color: '#1f2a24' }}
            />
          )}
          {eventos.map((e, i) => (
            <ReferenceLine
              key={i}
              x={String(e.data).slice(0, 10)}
              stroke={COR_SEVERIDADE[e.severidade] ?? '#5d6b62'}
              strokeDasharray="4 3"
              ifOverflow="extendDomain"
            />
          ))}
          {series.map((s) => (
            <Line
              key={s.id}
              type="monotone"
              dataKey={s.id}
              name={s.nome}
              stroke={s.cor}
              strokeWidth={2}
              strokeDasharray={s.tracejado ? '6 4' : undefined}
              dot={false}
              activeDot={{ r: 4, stroke: '#fff', strokeWidth: 2 }}
              connectNulls
              isAnimationActive={false}
              label={rotulosDiretos && multiplas ? rotuloFinal(s, linhas.length) : undefined}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
