import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'

import { mensagemErro } from '../api/client'
import { climaDiario } from '../api/clima'
import { listarDiagnosticos, rodarDiagnostico } from '../api/diagnosticos'
import { metricasTalhao, obterTalhao, soloTalhao } from '../api/talhoes'
import BarrasChart from '../components/charts/BarrasChart'
import LinhasChart from '../components/charts/LinhasChart'
import DiagnosticoPainel from '../components/DiagnosticoPainel'
import {
  Button,
  ErrorMessage,
  Field,
  Loading,
  Panel,
  SeverityBadge,
  SistemaTag,
  Stat,
  Tabs,
  inputClass,
} from '../components/ui'
import { useAuth } from '../context/AuthContext'
import { COR_SISTEMA, FINALIDADE, TIPO_DIAGNOSTICO, data, dataCurta, numero } from '../lib/format'

const ABAS = [
  { id: 'metricas', rotulo: 'Métricas' },
  { id: 'solo', rotulo: 'Solo' },
  { id: 'clima', rotulo: 'Clima' },
  { id: 'diagnosticos', rotulo: 'Diagnósticos' },
]

function AbaMetricas({ talhao }) {
  const { data: metricas = [], isLoading } = useQuery({
    queryKey: ['metricas', talhao.id],
    queryFn: () => metricasTalhao(talhao.id),
  })
  const { data: diags = [] } = useQuery({
    queryKey: ['diagnosticos', { talhao_id: talhao.id }],
    queryFn: () => listarDiagnosticos({ talhao_id: talhao.id }),
  })
  if (isLoading) return <Loading />

  const ndvi = metricas.filter((m) => m.ndvi_medio !== null)
  const balanco = metricas.filter((m) => m.balanco_hidrico_mm !== null)
  const produtividade = metricas.filter((m) => m.produtividade_kg_ha !== null)
  const eventos = diags
    .filter((d) => d.severidade !== 'BAIXA')
    .map((d) => ({ data: d.criado_em, severidade: d.severidade }))

  return (
    <div className="space-y-6">
      <Panel titulo="NDVI médio">
        <LinhasChart
          series={[
            {
              id: 'ndvi',
              nome: 'NDVI médio',
              cor: COR_SISTEMA[talhao.sistema],
              pontos: ndvi.map((m) => ({ data: m.data, valor: m.ndvi_medio })),
            },
          ]}
          dominio={[0, 1]}
          eventos={eventos}
        />
        <p className="mt-2 text-xs text-muted">
          Linhas verticais marcam diagnósticos com alerta: vermelho para dano, amarelo para atenção.
        </p>
      </Panel>
      <div className="grid gap-6 lg:grid-cols-2">
        <Panel titulo="Balanço hídrico de 7 dias">
          <BarrasChart
            dados={balanco.map((m) => ({ x: m.data, balanco: m.balanco_hidrico_mm }))}
            barras={[{ chave: 'balanco', nome: 'Chuva − ETP', cor: '#4a6fa5' }]}
            unidade=" mm"
          />
        </Panel>
        <Panel titulo="Produtividade">
          {produtividade.length === 0 ? (
            <p className="py-10 text-center text-sm text-muted">Colheita ainda não registrada.</p>
          ) : (
            <ul className="space-y-2">
              {produtividade.map((m) => (
                <li
                  key={m.data}
                  className="flex items-baseline justify-between border-b border-line pb-2 last:border-0"
                >
                  <span className="text-muted">Colheita de {data(m.data)}</span>
                  <span className="font-display text-3xl font-semibold tabular">
                    {numero(m.produtividade_kg_ha, 0)} <span className="text-base text-muted">kg/ha</span>
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>
    </div>
  )
}

const ROTULO_CLASSE = { BAIXO: 'text-alarm font-semibold', ADEQUADO: '' }

function AbaSolo({ talhaoId }) {
  const { data: pontos = [], isLoading } = useQuery({
    queryKey: ['solo', talhaoId],
    queryFn: () => soloTalhao(talhaoId),
  })
  if (isLoading) return <Loading />
  if (pontos.length === 0)
    return (
      <p className="text-sm text-muted">Sem análise de solo. Envie a planilha do Cropman em Enviar dados.</p>
    )
  const campos = [
    ['ph', 'pH', 2],
    ['mo', 'MO', 1],
    ['p', 'P', 1],
    ['k', 'K', 2],
    ['ca', 'Ca', 2],
    ['mg', 'Mg', 2],
    ['ctc', 'CTC', 2],
    ['v_pct', 'V%', 1],
  ]
  return (
    <Panel titulo={`Análise de ${data(pontos[0].data_coleta)}`}>
      <div className="relative overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-muted">
            <tr className="border-b border-line">
              <th className="px-3 py-2 text-left font-medium">Ponto</th>
              <th className="px-3 py-2 text-left font-medium">Zona</th>
              {campos.map(([c, r]) => (
                <th key={c} className="px-3 py-2 text-right font-medium">
                  {r}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {pontos.map((p) => (
              <tr key={p.id} className="border-b border-line last:border-0">
                <td className="px-3 py-2 font-medium">{p.ponto}</td>
                <td className="px-3 py-2">{p.zona ?? '—'}</td>
                {campos.map(([c, , casas]) => (
                  <td
                    key={c}
                    className={`px-3 py-2 text-right tabular ${ROTULO_CLASSE[p.classificacao[c]] ?? ''}`}
                  >
                    {numero(p[c], casas)}
                    {p.classificacao[c] === 'BAIXO' && <span className="sr-only"> (abaixo do mínimo)</span>}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-3 text-xs text-muted">
        Valores em vermelho estão abaixo do mínimo configurado para pH, V%, P e K.
      </p>
    </Panel>
  )
}

function AbaClima({ metricas }) {
  const datas = metricas.map((m) => m.data).sort()
  const [de, setDe] = useState(datas[0] ?? '')
  const [ate, setAte] = useState(datas[datas.length - 1] ?? '')
  const { data: dias = [], isLoading } = useQuery({
    queryKey: ['clima', de, ate],
    queryFn: () => climaDiario({ de: de || undefined, ate: ate || undefined }),
  })
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap gap-3">
        <Field label="De">
          <input type="date" value={de} onChange={(e) => setDe(e.target.value)} className={inputClass} />
        </Field>
        <Field label="Até">
          <input type="date" value={ate} onChange={(e) => setAte(e.target.value)} className={inputClass} />
        </Field>
      </div>
      {isLoading ? (
        <Loading />
      ) : (
        <div className="grid gap-6 lg:grid-cols-2">
          <Panel titulo="Temperatura média diária">
            <LinhasChart
              series={[
                {
                  id: 't',
                  nome: 'Temperatura',
                  cor: '#b5541c',
                  pontos: dias.map((d) => ({ data: d.data, valor: d.temp_med })),
                },
              ]}
              casas={1}
              unidade=" °C"
            />
          </Panel>
          <Panel titulo="Chuva diária">
            <BarrasChart
              dados={dias.map((d) => ({ x: d.data, chuva: d.chuva_mm }))}
              barras={[{ chave: 'chuva', nome: 'Chuva', cor: '#4a6fa5' }]}
              unidade=" mm"
              altura={280}
            />
          </Panel>
        </div>
      )}
      <p className="text-xs text-muted">Clima da estação da fazenda, igual para todos os talhões.</p>
    </div>
  )
}

function AbaDiagnosticos({ talhaoId, focado }) {
  const { data: diags = [], isLoading } = useQuery({
    queryKey: ['diagnosticos', { talhao_id: talhaoId }],
    queryFn: () => listarDiagnosticos({ talhao_id: talhaoId }),
  })
  const [, setParams] = useSearchParams()
  if (isLoading) return <Loading />
  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
      <ul className="max-h-[70vh] divide-y divide-line overflow-y-auto rounded-md border border-line bg-panel">
        {diags.length === 0 && (
          <li className="px-4 py-6 text-center text-sm text-muted">Nenhum diagnóstico para este talhão.</li>
        )}
        {diags.map((d) => (
          <li key={d.id}>
            <button
              type="button"
              onClick={() => setParams({ aba: 'diagnosticos', diagnostico: d.id })}
              aria-current={focado === d.id}
              className={`flex w-full items-center gap-3 px-4 py-2.5 text-left text-sm ${focado === d.id ? 'bg-canopy-soft' : 'hover:bg-paper'}`}
            >
              <span className="w-12 text-muted tabular">{dataCurta(d.criado_em)}</span>
              <SeverityBadge severidade={d.severidade} />
              <span className="min-w-0 flex-1 truncate">
                {TIPO_DIAGNOSTICO[d.tipo]}
                {d.praga_nome ? `: ${d.praga_nome}` : ''}
              </span>
            </button>
          </li>
        ))}
      </ul>
      <Panel>
        {focado ? (
          <DiagnosticoPainel id={focado} compacto />
        ) : (
          <p className="py-10 text-center text-sm text-muted">Escolha um diagnóstico na lista.</p>
        )}
      </Panel>
    </div>
  )
}

export default function TalhaoDetalhe() {
  const { id } = useParams()
  const talhaoId = Number(id)
  const [params, setParams] = useSearchParams()
  const focado = params.get('diagnostico') ? Number(params.get('diagnostico')) : null
  const aba = params.get('aba') ?? (focado ? 'diagnosticos' : 'metricas')
  const { isAgronomo } = useAuth()
  const queryClient = useQueryClient()

  const {
    data: talhao,
    isLoading,
    error,
  } = useQuery({ queryKey: ['talhao', talhaoId], queryFn: () => obterTalhao(talhaoId) })
  const { data: metricas = [] } = useQuery({
    queryKey: ['metricas', talhaoId],
    queryFn: () => metricasTalhao(talhaoId),
  })
  const rodar = useMutation({
    mutationFn: () => rodarDiagnostico(talhaoId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['diagnosticos'] })
      queryClient.invalidateQueries({ queryKey: ['alertas'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
    },
  })

  if (isLoading) return <Loading />
  if (error) return <ErrorMessage>{mensagemErro(error)}</ErrorMessage>

  const m = talhao.ultima_metrica
  return (
    <>
      <nav className="mb-2 text-sm text-muted">
        <Link to="/talhoes" className="hover:text-canopy">
          Talhões
        </Link>{' '}
        / {talhao.nome}
      </nav>
      <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-4xl font-semibold">{talhao.nome}</h1>
          <div className="mt-2 flex flex-wrap items-center gap-3 text-sm text-muted">
            <SistemaTag sistema={talhao.sistema} />
            <span>{FINALIDADE[talhao.finalidade]}</span>
            <span>{talhao.cultura}</span>
            <span className="tabular">{numero(talhao.area_ha, 2)} ha</span>
          </div>
        </div>
        {isAgronomo && (
          <div className="text-right">
            <Button onClick={() => rodar.mutate()} disabled={rodar.isPending}>
              {rodar.isPending ? 'Analisando…' : 'Rodar diagnóstico'}
            </Button>
            {rodar.isSuccess && (
              <p className="mt-1 text-xs text-muted">
                {rodar.data.length === 0
                  ? 'Nenhum problema novo encontrado.'
                  : `${rodar.data.length} diagnóstico(s) novo(s).`}
              </p>
            )}
            <ErrorMessage>{rodar.error && mensagemErro(rodar.error)}</ErrorMessage>
          </div>
        )}
      </header>

      <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat
          rotulo="Último NDVI"
          valor={numero(m?.ndvi_medio, 2)}
          detalhe={m ? `Leitura de ${data(m.data)}` : 'Sem leitura'}
          tom="canopy"
        />
        <Stat
          rotulo="Faixa na leitura"
          valor={m?.ndvi_min != null ? `${numero(m.ndvi_min, 2)}–${numero(m.ndvi_max, 2)}` : '—'}
          detalhe="Mínimo e máximo no talhão"
        />
        <Stat
          rotulo="Balanço hídrico"
          valor={m?.balanco_hidrico_mm != null ? `${numero(m.balanco_hidrico_mm, 1)} mm` : '—'}
          detalhe="Chuva menos ETP em 7 dias"
          tom={m?.balanco_hidrico_mm < -25 ? 'alarm' : undefined}
        />
        <Stat
          rotulo="Leituras de NDVI"
          valor={metricas.filter((x) => x.ndvi_medio !== null).length}
          detalhe="Nesta safra"
        />
      </div>

      <Tabs
        abas={ABAS}
        ativa={aba}
        onTrocar={(nova) =>
          setParams(nova === 'diagnosticos' && focado ? { aba: nova, diagnostico: focado } : { aba: nova })
        }
      />
      {aba === 'metricas' && <AbaMetricas talhao={talhao} />}
      {aba === 'solo' && <AbaSolo talhaoId={talhaoId} />}
      {aba === 'clima' && <AbaClima key={metricas.length} metricas={metricas} />}
      {aba === 'diagnosticos' && <AbaDiagnosticos talhaoId={talhaoId} focado={focado} />}
    </>
  )
}
