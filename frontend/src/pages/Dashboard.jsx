import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'

import { mensagemErro } from '../api/client'
import { resumoDashboard } from '../api/dashboard'
import { listarDiagnosticos } from '../api/diagnosticos'
import LinhasChart from '../components/charts/LinhasChart'
import MapaTalhoes from '../components/MapaTalhoes'
import { ErrorMessage, Loading, PageHeader, Panel, SeverityBadge, Stat } from '../components/ui'
import { COR_SISTEMA, dataCurta, numero } from '../lib/format'

export default function Dashboard() {
  const { data: resumo, isLoading, error } = useQuery({ queryKey: ['dashboard'], queryFn: resumoDashboard })
  const { data: recentes = [] } = useQuery({
    queryKey: ['diagnosticos', 'recentes'],
    queryFn: () => listarDiagnosticos(),
  })

  if (isLoading) return <Loading />
  if (error) return <ErrorMessage>{mensagemErro(error)}</ErrorMessage>

  const { cards } = resumo
  const series = resumo.ndvi_por_talhao.map((t) => {
    const talhao = resumo.talhoes.find((x) => x.id === t.talhao_id)
    return {
      id: `t${t.talhao_id}`,
      nome: t.nome,
      cor: COR_SISTEMA[t.sistema],
      tracejado: talhao?.finalidade === 'SILAGEM',
      pontos: t.serie.map((p) => ({ data: p.data, valor: p.ndvi })),
    }
  })

  return (
    <>
      <PageHeader
        titulo="Painel da fazenda"
        descricao="Onde olhar primeiro: alertas abertos, vigor das lavouras e o mapa dos talhões."
      />

      <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat
          rotulo="Talhões monitorados"
          valor={cards.talhoes}
          detalhe={`${numero(cards.area_total_ha, 1)} ha no total`}
        />
        <Stat
          rotulo="Alertas abertos"
          valor={cards.alertas_abertos}
          detalhe={
            cards.alertas_altos ? `${cards.alertas_altos} em nível de dano` : 'Nenhum em nível de dano'
          }
          tom={cards.alertas_altos ? 'alarm' : cards.alertas_abertos ? 'straw' : undefined}
        />
        <Stat
          rotulo="NDVI médio atual"
          valor={numero(cards.ndvi_medio_atual, 2)}
          detalhe="Média da última leitura de cada talhão"
          tom="canopy"
        />
        <Stat
          rotulo="Diagnósticos registrados"
          valor={cards.diagnosticos}
          detalhe="Pragas, vigor, solo e água"
        />
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
        <Panel titulo="Mapa dos talhões">
          <MapaTalhoes talhoes={resumo.talhoes} />
        </Panel>
        <Panel titulo="NDVI por talhão">
          <LinhasChart series={series} dominio={[0, 1]} altura={360} />
          <p className="mt-2 text-xs text-muted">Linha contínua: grão. Tracejada: silagem.</p>
        </Panel>
      </div>

      <Panel
        titulo="Diagnósticos recentes"
        className="mt-6"
        acao={
          <Link to="/diagnosticos" className="text-sm font-medium text-canopy hover:underline">
            Ver todos
          </Link>
        }
      >
        {recentes.length === 0 ? (
          <p className="text-sm text-muted">
            Nenhum diagnóstico ainda. Rode o diagnóstico na página de um talhão.
          </p>
        ) : (
          <ul className="divide-y divide-line">
            {recentes.slice(0, 6).map((d) => (
              <li key={d.id}>
                <Link
                  to={`/diagnosticos/${d.id}`}
                  className="flex items-center gap-3 py-2.5 text-sm hover:text-canopy"
                >
                  <span className="w-12 text-muted tabular">{dataCurta(d.criado_em)}</span>
                  <SeverityBadge severidade={d.severidade} />
                  <span className="min-w-0 flex-1 truncate">{d.resumo}</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </>
  )
}
