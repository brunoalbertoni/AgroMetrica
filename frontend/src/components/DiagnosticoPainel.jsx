import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'

import { mensagemErro } from '../api/client'
import { obterDiagnostico } from '../api/diagnosticos'
import { alterarPrescricao } from '../api/prescricoes'
import { useAuth } from '../context/AuthContext'
import { STATUS_PRESCRICAO, TIPO_DIAGNOSTICO, data, dataHora, numero } from '../lib/format'
import BBoxCanvas from './BBoxCanvas'
import ImageCompare from './ImageCompare'
import { Button, ErrorMessage, Loading, SeverityBadge } from './ui'

function rotuloIndice(indice) {
  // Foto RGB nunca é chamada de NDVI.
  if (indice === 'VARI') return 'índice RGB (VARI)'
  if (indice === 'NDVI') return 'NDVI'
  return 'Processada'
}

function Detalhes({ diag }) {
  const d = diag.detalhes ?? {}
  const linhas = []
  if (diag.tipo === 'PRAGA') {
    linhas.push(['Contagem na armadilha', numero(d.contagem)])
    if (d.limiares) {
      linhas.push(['Limiar de alerta', numero(d.limiares.alerta)])
      linhas.push(['Limiar de controle', numero(d.limiares.controle)])
      linhas.push(['Limiar de dano', numero(d.limiares.dano)])
    }
  } else if (diag.tipo === 'VIGOR') {
    linhas.push([`NDVI em ${data(d.data_anterior)}`, numero(d.ndvi_anterior, 2)])
    linhas.push([`NDVI em ${data(d.data)}`, numero(d.ndvi_atual, 2)])
    linhas.push(['Queda', `${numero(d.queda_pct, 1)}%`])
  } else if (diag.tipo === 'HIDRICO') {
    linhas.push([`Balanço de ${d.janela_dias} dias até ${data(d.data)}`, `${numero(d.balanco_mm, 1)} mm`])
    linhas.push(['Limite configurado', `${numero(d.limite_mm, 0)} mm`])
  } else if (diag.tipo === 'NUTRICIONAL') {
    linhas.push(['Coleta', data(d.data)])
    linhas.push(['Pontos com problema', `${d.pontos?.length ?? 0} de ${d.pontos_avaliados ?? '?'}`])
  }
  return (
    <div>
      <dl className="grid grid-cols-[1fr_auto] gap-x-6 gap-y-1.5 text-sm">
        {linhas.map(([k, v]) => (
          <div key={k} className="contents">
            <dt className="text-muted">{k}</dt>
            <dd className="text-right font-medium tabular">{v}</dd>
          </div>
        ))}
      </dl>
      {diag.tipo === 'NUTRICIONAL' && d.pontos?.length > 0 && (
        <ul className="mt-3 space-y-1 text-sm">
          {d.pontos.map((p) => (
            <li key={p.ponto}>
              <span className="font-medium">{p.ponto}:</span> {p.problemas.join('; ')}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function Prescricoes({ diag }) {
  const { isAgronomo } = useAuth()
  const queryClient = useQueryClient()
  const mudar = useMutation({
    mutationFn: ({ id, status }) => alterarPrescricao(id, status),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['diagnostico', diag.id] }),
  })

  if (diag.tipo !== 'PRAGA') return null
  return (
    <section className="mt-6">
      <h3 className="text-lg font-semibold">Prescrição sugerida</h3>
      <p className="mt-1 rounded border border-straw/60 bg-straw-soft px-3 py-2 text-sm text-ink">
        Recomendação automática, a validar por um responsável técnico (engenheiro agrônomo) antes da
        aplicação. Siga sempre a bula e o receituário agronômico.
      </p>
      {diag.prescricoes.length === 0 ? (
        <p className="mt-3 text-sm text-muted">
          Nenhum produto cadastrado para esta praga. Vincule produtos em{' '}
          <Link to="/produtos" className="text-canopy underline">
            Produtos
          </Link>
          .
        </p>
      ) : (
        <ul className="mt-3 divide-y divide-line rounded border border-line">
          {diag.prescricoes.map((p) => (
            <li key={p.id} className="flex flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3 text-sm">
              <div className="min-w-48 flex-1">
                <p className="font-medium">{p.produto.nome_comercial}</p>
                <p className="text-muted">{p.produto.ingrediente_ativo}</p>
              </div>
              <div>
                <p className="text-muted">Dose</p>
                <p className="font-medium tabular">
                  {numero(p.dose, 2)} {p.unidade}
                </p>
              </div>
              <div>
                <p className="text-muted">Janela de aplicação</p>
                <p className="font-medium tabular">
                  {p.janela_inicio
                    ? `${dataHora(p.janela_inicio)} a ${dataHora(p.janela_fim)}`
                    : 'Sem janela favorável nos próximos dias'}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <span className="rounded-sm border border-line px-2 py-0.5 text-xs font-medium">
                  {STATUS_PRESCRICAO[p.status]}
                </span>
                {isAgronomo && p.status === 'SUGERIDA' && (
                  <>
                    <Button
                      onClick={() => mudar.mutate({ id: p.id, status: 'APROVADA' })}
                      disabled={mudar.isPending}
                    >
                      Aprovar
                    </Button>
                    <Button
                      variante="secundario"
                      onClick={() => mudar.mutate({ id: p.id, status: 'DESCARTADA' })}
                      disabled={mudar.isPending}
                    >
                      Descartar
                    </Button>
                  </>
                )}
                {isAgronomo && p.status === 'APROVADA' && (
                  <Button
                    variante="secundario"
                    onClick={() => mudar.mutate({ id: p.id, status: 'APLICADA' })}
                    disabled={mudar.isPending}
                  >
                    Registrar aplicação
                  </Button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
      <div className="mt-2">
        <ErrorMessage>{mudar.error && mensagemErro(mudar.error)}</ErrorMessage>
      </div>
      <p className="mt-2 text-xs text-muted">
        Janela: vento abaixo de 10 km/h, umidade acima de 55%, temperatura abaixo de 30 °C e sem chuva nas 2
        horas seguintes.
      </p>
    </section>
  )
}

/** Detalhe completo de um diagnóstico: imagem (com caixas ou comparação), números da regra e prescrições. */
export default function DiagnosticoPainel({ id, compacto = false }) {
  const {
    data: diag,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['diagnostico', Number(id)],
    queryFn: () => obterDiagnostico(id),
  })

  if (isLoading) return <Loading />
  if (error) return <ErrorMessage>{mensagemErro(error)}</ErrorMessage>

  const img = diag.imagem
  return (
    <article>
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <SeverityBadge severidade={diag.severidade} />
            <span className="text-sm text-muted">
              {TIPO_DIAGNOSTICO[diag.tipo]} em {dataHora(diag.criado_em)}
            </span>
          </div>
          <h2 className={`mt-1 font-semibold ${compacto ? 'text-xl' : 'text-2xl'}`}>{diag.resumo}</h2>
        </div>
        {compacto && (
          <Link to={`/diagnosticos/${diag.id}`} className="text-sm font-medium text-canopy hover:underline">
            Abrir página do diagnóstico
          </Link>
        )}
      </header>

      <div className={`mt-4 grid gap-6 ${img ? 'lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]' : ''}`}>
        {img && (
          <div>
            {diag.bboxes.length > 0 || !img.url_processada ? (
              <BBoxCanvas src={img.url} caixas={diag.bboxes} alt={`Imagem do diagnóstico ${diag.id}`} />
            ) : (
              <ImageCompare
                original={img.url}
                processada={img.url_processada}
                rotulo={rotuloIndice(img.indice)}
                alt="Imagem do talhão"
              />
            )}
          </div>
        )}
        <div>
          <Detalhes diag={diag} />
          {!compacto && (
            <p className="mt-4 text-sm">
              Talhão:{' '}
              <Link to={`/talhoes/${diag.talhao_id}`} className="font-medium text-canopy hover:underline">
                {diag.talhao_nome}
              </Link>
            </p>
          )}
        </div>
      </div>
      <Prescricoes diag={diag} />
    </article>
  )
}
