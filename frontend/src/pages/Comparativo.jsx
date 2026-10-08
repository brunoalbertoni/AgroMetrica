import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import { mensagemErro } from '../api/client'
import { comparativo } from '../api/dashboard'
import { listarTalhoes } from '../api/talhoes'
import BarrasChart from '../components/charts/BarrasChart'
import LinhasChart from '../components/charts/LinhasChart'
import {
  ErrorMessage,
  Field,
  Loading,
  PageHeader,
  Panel,
  SeverityBadge,
  SistemaTag,
  inputClass,
} from '../components/ui'
import { COR_SISTEMA, TIPO_DIAGNOSTICO, dataCurta, numero } from '../lib/format'

function padrao(talhoes, sistema) {
  return (
    talhoes.find((t) => t.sistema === sistema && t.finalidade === 'GRAO') ??
    talhoes.find((t) => t.sistema === sistema) ??
    talhoes[0]
  )
}

function Indicador({ rotulo, a, b, casas = 0, unidade = '', maiorMelhor = true }) {
  const diff = a != null && b != null && b !== 0 ? ((a - b) / Math.abs(b)) * 100 : null
  const favoravel = diff != null && (maiorMelhor ? diff > 0 : diff < 0)
  return (
    <div className="rounded-md border border-line bg-panel px-4 py-3">
      <p className="text-sm text-muted">{rotulo}</p>
      <div className="mt-1 flex items-baseline gap-4">
        <p className="font-display text-3xl font-semibold tabular" style={{ color: COR_SISTEMA.AGRO_4_0 }}>
          {numero(a, casas)}
          <span className="text-base">{unidade}</span>
        </p>
        <p
          className="font-display text-2xl font-semibold tabular"
          style={{ color: COR_SISTEMA.CONVENCIONAL }}
        >
          {numero(b, casas)}
          <span className="text-base">{unidade}</span>
        </p>
      </div>
      {diff != null && (
        <p className={`text-xs ${favoravel ? 'text-canopy' : 'text-muted'}`}>
          A {diff >= 0 ? '+' : ''}
          {numero(diff, 1)}% em relação a B
        </p>
      )}
    </div>
  )
}

export default function Comparativo() {
  const { data: pagina, isLoading: carregandoTalhoes } = useQuery({
    queryKey: ['talhoes', 'todos'],
    queryFn: () => listarTalhoes({ size: 200 }),
  })
  const talhoes = pagina?.items ?? []
  const [escolha, setEscolha] = useState({ a: '', b: '' })
  const a = escolha.a || padrao(talhoes, 'AGRO_4_0')?.id
  const b = escolha.b || padrao(talhoes, 'CONVENCIONAL')?.id

  const {
    data: c,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['comparativo', a, b],
    queryFn: () => comparativo(a, b),
    enabled: Boolean(a && b),
  })

  if (carregandoTalhoes) return <Loading />

  const serie = (bloco, chave, campo, sufixo = '') => ({
    id: `${chave}${sufixo}`,
    nome: bloco.talhao.nome,
    cor: COR_SISTEMA[bloco.talhao.sistema],
    tracejado: chave === 'b' && bloco.talhao.sistema === c?.a.talhao.sistema,
    pontos: bloco[campo.lista].map((p) => ({ data: p.data, valor: p[campo.valor] })),
  })

  const eventos =
    c?.eventos
      .filter((e) => e.severidade !== 'BAIXA')
      .map((e) => ({ data: e.data, severidade: e.severidade })) ?? []

  // pragas: soma semanal das contagens por talhão
  const pragas = (() => {
    if (!c) return []
    const mapa = new Map()
    for (const [chave, bloco] of [
      ['a', c.a],
      ['b', c.b],
    ]) {
      for (const p of bloco.pragas) {
        const dia = String(p.data).slice(0, 10)
        if (!mapa.has(dia)) mapa.set(dia, { x: dia, a: 0, b: 0 })
        mapa.get(dia)[chave] += p.contagem ?? 0
      }
    }
    return [...mapa.values()].sort((x, y) => x.x.localeCompare(y.x))
  })()

  return (
    <>
      <PageHeader
        titulo="4.0 × Convencional"
        descricao="Os mesmos indicadores de dois talhões lado a lado, com os eventos da safra marcados nas séries."
      />

      <div className="mb-6 grid gap-3 sm:grid-cols-2">
        {[
          ['a', 'Talhão A', a],
          ['b', 'Talhão B', b],
        ].map(([k, rotulo, valor]) => (
          <Field key={k} label={rotulo}>
            <select
              value={valor ?? ''}
              onChange={(e) => setEscolha((s) => ({ ...s, [k]: Number(e.target.value) }))}
              className={inputClass}
            >
              {talhoes.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.nome}
                </option>
              ))}
            </select>
          </Field>
        ))}
      </div>

      <ErrorMessage>{error && mensagemErro(error)}</ErrorMessage>
      {isLoading || !c ? (
        <Loading />
      ) : (
        <div className="space-y-6">
          <div className="flex flex-wrap items-center gap-4 text-sm">
            <span className="flex items-center gap-2">
              A: <strong>{c.a.talhao.nome}</strong> <SistemaTag sistema={c.a.talhao.sistema} />
            </span>
            <span className="flex items-center gap-2">
              B: <strong>{c.b.talhao.nome}</strong> <SistemaTag sistema={c.b.talhao.sistema} />
            </span>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <Indicador
              rotulo="Produtividade (kg/ha)"
              a={c.a.indicadores.produtividade_kg_ha}
              b={c.b.indicadores.produtividade_kg_ha}
            />
            <Indicador
              rotulo="NDVI de pico"
              a={c.a.indicadores.ndvi_maximo}
              b={c.b.indicadores.ndvi_maximo}
              casas={2}
            />
            <Indicador
              rotulo="NDVI médio da safra"
              a={c.a.indicadores.ndvi_medio_periodo}
              b={c.b.indicadores.ndvi_medio_periodo}
              casas={2}
            />
            <Indicador
              rotulo="Pragas capturadas"
              a={c.a.indicadores.total_pragas}
              b={c.b.indicadores.total_pragas}
              maiorMelhor={false}
            />
          </div>

          <Panel titulo="NDVI ao longo da safra">
            <LinhasChart
              series={[
                serie(c.a, 'a', { lista: 'ndvi', valor: 'ndvi_medio' }),
                serie(c.b, 'b', { lista: 'ndvi', valor: 'ndvi_medio' }),
              ]}
              dominio={[0, 1]}
              altura={340}
              eventos={eventos}
            />
            <p className="mt-2 text-xs text-muted">
              Linhas verticais: diagnósticos com alerta (vermelho = dano, amarelo = atenção).
            </p>
          </Panel>

          <div className="grid gap-6 lg:grid-cols-2">
            <Panel titulo="Pragas nas armadilhas">
              <BarrasChart
                dados={pragas}
                barras={[
                  { chave: 'a', nome: c.a.talhao.nome, cor: COR_SISTEMA[c.a.talhao.sistema] },
                  {
                    chave: 'b',
                    nome: c.b.talhao.nome,
                    cor:
                      c.a.talhao.sistema === c.b.talhao.sistema ? '#8fb8ad' : COR_SISTEMA[c.b.talhao.sistema],
                  },
                ]}
                casas={0}
                altura={280}
              />
            </Panel>
            <Panel titulo="Produtividade na colheita">
              <BarrasChart
                dados={[
                  {
                    x: c.a.talhao.nome,
                    valor: c.a.indicadores.produtividade_kg_ha,
                    cor: COR_SISTEMA[c.a.talhao.sistema],
                  },
                  {
                    x: c.b.talhao.nome,
                    valor: c.b.indicadores.produtividade_kg_ha,
                    cor: COR_SISTEMA[c.b.talhao.sistema],
                  },
                ].filter((d) => d.valor != null)}
                barras={[{ chave: 'valor', nome: 'Produtividade', cor: '#5d6b62' }]}
                eixoData={false}
                corPorLinha
                casas={0}
                unidade=" kg/ha"
                altura={280}
              />
            </Panel>
          </div>

          <Panel titulo="Manejo">
            {c.a.operacoes.length + c.b.operacoes.length === 0 ? (
              <p className="text-sm text-muted">Nenhuma operação de máquina registrada nesses talhões.</p>
            ) : (
              <div className="relative overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="text-muted">
                    <tr className="border-b border-line">
                      <th className="px-3 py-2 text-left font-medium">Operação</th>
                      <th className="px-3 py-2 text-right font-medium">A: {c.a.talhao.nome}</th>
                      <th className="px-3 py-2 text-right font-medium">B: {c.b.talhao.nome}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[...new Set([...c.a.operacoes, ...c.b.operacoes].map((o) => o.operacao))].map((nome) => (
                      <tr key={nome} className="border-b border-line last:border-0">
                        <td className="px-3 py-2 font-medium">{nome}</td>
                        {[c.a, c.b].map((bloco) => {
                          const o = bloco.operacoes.find((x) => x.operacao === nome)
                          return (
                            <td key={bloco.talhao.id} className="px-3 py-2 text-right tabular">
                              {o ? (
                                <>
                                  {numero(o.dose_aplicada, 0)} {o.unidade}
                                  <span className="block text-xs text-muted">{dataCurta(o.data_inicio)}</span>
                                </>
                              ) : (
                                '—'
                              )}
                            </td>
                          )
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>

          <div className="grid gap-6 lg:grid-cols-2">
            <Panel titulo="Chuva diária">
              <BarrasChart
                dados={c.clima.map((d) => ({ x: d.data, chuva: d.chuva_mm }))}
                barras={[{ chave: 'chuva', nome: 'Chuva', cor: '#4a6fa5' }]}
                unidade=" mm"
              />
            </Panel>
            <Panel titulo="Temperatura média diária">
              <LinhasChart
                series={[
                  {
                    id: 't',
                    nome: 'Temperatura',
                    cor: '#b5541c',
                    pontos: c.clima.map((d) => ({ data: d.data, valor: d.temp_med })),
                  },
                ]}
                casas={1}
                unidade=" °C"
                altura={220}
              />
            </Panel>
          </div>

          <Panel titulo="Eventos da safra">
            {c.eventos.length === 0 ? (
              <p className="text-sm text-muted">Nenhum diagnóstico registrado nesses talhões.</p>
            ) : (
              <ul className="max-h-80 divide-y divide-line overflow-y-auto">
                {c.eventos.map((e) => (
                  <li key={e.diagnostico_id}>
                    <Link
                      to={`/diagnosticos/${e.diagnostico_id}`}
                      className="flex items-center gap-3 py-2 text-sm hover:text-canopy"
                    >
                      <span className="w-12 text-muted tabular">{dataCurta(e.data)}</span>
                      <span className="w-6 font-semibold">{e.talhao_id === c.a.talhao.id ? 'A' : 'B'}</span>
                      <SeverityBadge severidade={e.severidade} />
                      <span className="w-24 text-muted">{TIPO_DIAGNOSTICO[e.tipo]}</span>
                      <span className="min-w-0 flex-1 truncate">{e.resumo}</span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </div>
      )}
    </>
  )
}
