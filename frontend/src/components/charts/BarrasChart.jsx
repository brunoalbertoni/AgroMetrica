import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { dataCurta, data as fmtData, numero } from '../../lib/format'

const EIXO = { stroke: '#5d6b62', fontSize: 12 }

function Dica({ active, payload, label, casas, unidade, rotuloX }) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded border border-line bg-panel px-3 py-2 text-xs shadow-md">
      <p className="mb-1 font-medium text-ink">{rotuloX(label)}</p>
      {payload.map((p) => (
        <p key={p.dataKey} className="flex items-center gap-2">
          <span
            className="inline-block h-2 w-2 rounded-sm"
            style={{ background: p.color ?? p.payload?.cor }}
            aria-hidden
          />
          <span className="text-muted">{p.name}</span>
          <span className="ml-auto pl-3 font-medium tabular text-ink">
            {numero(p.value, casas)}
            {unidade}
          </span>
        </p>
      ))}
    </div>
  )
}

/**
 * Barras verticais. `barras`: [{ chave, nome, cor }]; `dados`: linhas com `x` + uma chave por barra.
 * Com `corPorLinha`, cada barra usa `linha.cor` (ex.: produtividade por talhão).
 */
export default function BarrasChart({
  dados,
  barras,
  altura = 220,
  casas = 1,
  unidade = '',
  eixoData = true,
  corPorLinha = false,
}) {
  if (!dados?.length) return <p className="py-10 text-center text-sm text-muted">Sem dados no período.</p>
  const rotuloX = eixoData ? fmtData : (v) => v
  return (
    <div style={{ height: altura }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={dados} margin={{ top: 8, right: 16, left: 0, bottom: 0 }} barGap={2}>
          <CartesianGrid stroke="#e7eae3" vertical={false} />
          <XAxis
            dataKey="x"
            tickFormatter={eixoData ? dataCurta : undefined}
            tick={EIXO}
            tickLine={false}
            axisLine={{ stroke: '#d8ddd3' }}
            minTickGap={16}
          />
          <YAxis
            tick={EIXO}
            tickLine={false}
            axisLine={false}
            width={56}
            tickFormatter={(v) => numero(v, 0)}
          />
          <Tooltip
            content={<Dica casas={casas} unidade={unidade} rotuloX={rotuloX} />}
            cursor={{ fill: '#1f2a2410' }}
          />
          {barras.length > 1 && (
            <Legend verticalAlign="top" height={28} wrapperStyle={{ fontSize: 12, color: '#1f2a24' }} />
          )}
          {barras.map((b) => (
            <Bar
              key={b.chave}
              dataKey={b.chave}
              name={b.nome}
              fill={b.cor}
              radius={[4, 4, 0, 0]}
              maxBarSize={48}
              isAnimationActive={false}
            >
              {corPorLinha && dados.map((linha) => <Cell key={linha.x} fill={linha.cor} />)}
            </Bar>
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
