import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import {
  analisarMensagem,
  criarMensagem,
  decidirMensagem,
  listarMensagens,
  resumoCampo,
} from '../../api/campo/CampoApi'
import { listarTalhoes } from '../../api/talhoes/TalhoesApi'
import { mensagemErro } from '../../compartilhado/client'
import { CATEGORIA_CAMPO, COR_CATEGORIA_CAMPO, DESTINO_CAMPO, dataHora } from '../../compartilhado/format'
import Markdown from '../../compartilhado/Markdown'
import {
  Button,
  EmptyState,
  ErrorMessage,
  Field,
  Loading,
  PageHeader,
  Panel,
  inputClass,
} from '../../compartilhado/ui'

const ABAS = [
  { id: 'CAIXA_DE_ENTRADA', rotulo: 'Caixa de entrada' },
  { id: 'ANOTACAO', rotulo: 'Anotações' },
  { id: 'DADO_SOLO', rotulo: 'Dados de solo' },
  { id: 'DESCARTADA', rotulo: 'Descartadas' },
  { id: '', rotulo: 'Todas' },
]

function Etiqueta({ categoria }) {
  return (
    <span
      className={`inline-block rounded-sm px-2 py-0.5 text-xs font-semibold ${COR_CATEGORIA_CAMPO[categoria]}`}
    >
      {CATEGORIA_CAMPO[categoria]}
    </span>
  )
}

function Cartao({ mensagem: m, talhoes }) {
  const queryClient = useQueryClient()
  const [nota, setNota] = useState(m.nota ?? '')
  const [editandoNota, setEditandoNota] = useState(false)
  const atualizarTudo = () => queryClient.invalidateQueries({ queryKey: ['campo'] })

  const decidir = useMutation({
    mutationFn: (dados) => decidirMensagem(m.id, dados),
    onSuccess: atualizarTudo,
  })
  const analisar = useMutation({ mutationFn: () => analisarMensagem(m.id), onSuccess: atualizarTudo })
  const erro = decidir.error ?? analisar.error
  const naCaixa = m.destino === 'CAIXA_DE_ENTRADA'

  return (
    <article
      className={`rounded-md border border-line bg-panel p-4 ${m.destino === 'DESCARTADA' ? 'opacity-60' : ''}`}
    >
      <header className="mb-2 flex flex-wrap items-center gap-2 text-sm">
        <span className="font-medium">{m.remetente || 'Sem remetente'}</span>
        <span className="text-muted">{dataHora(m.recebido_em)}</span>
        <span className="rounded-sm border border-line px-1.5 py-0.5 text-xs text-muted">
          {m.origem === 'whatsapp' ? 'WhatsApp' : 'Teste'}
        </span>
        <span className="ml-auto flex items-center gap-2">
          {m.talhao_nome && <span className="text-xs text-muted">Talhão: {m.talhao_nome}</span>}
          <Etiqueta categoria={m.categoria} />
        </span>
      </header>

      <p className="whitespace-pre-wrap text-[15px]">{m.texto}</p>
      {m.resumo && <p className="mt-1 text-sm italic text-muted">Resumo da IA: {m.resumo}</p>}
      {m.nota && !editandoNota && (
        <p className="mt-2 rounded border-l-4 border-straw bg-straw-soft px-3 py-1.5 text-sm">
          <span className="font-medium">Nota:</span> {m.nota}
        </p>
      )}

      {m.analise_ia && (
        <div className="mt-3 rounded-md border border-line bg-paper px-3 py-2 text-sm">
          <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted">Análise da IA</p>
          <Markdown>{m.analise_ia}</Markdown>
        </div>
      )}

      <div className="mt-3 flex flex-wrap items-end gap-3 border-t border-line pt-3">
        <label className="text-xs text-muted">
          Categoria
          <select
            className={`${inputClass} mt-1 py-1.5`}
            value={m.categoria}
            onChange={(e) => decidir.mutate({ categoria: e.target.value })}
          >
            {Object.entries(CATEGORIA_CAMPO).map(([valor, rotulo]) => (
              <option key={valor} value={valor}>
                {rotulo}
              </option>
            ))}
          </select>
        </label>
        <label className="text-xs text-muted">
          Talhão
          <select
            className={`${inputClass} mt-1 py-1.5`}
            value={m.talhao_id ?? ''}
            onChange={(e) => decidir.mutate({ talhao_id: e.target.value ? Number(e.target.value) : null })}
          >
            <option value="">Nenhum</option>
            {talhoes.map((t) => (
              <option key={t.id} value={t.id}>
                {t.nome}
              </option>
            ))}
          </select>
        </label>

        <div className="ml-auto flex flex-wrap items-center gap-2">
          {naCaixa ? (
            <>
              <Button
                variante="secundario"
                disabled={decidir.isPending}
                onClick={() => decidir.mutate({ destino: 'ANOTACAO' })}
              >
                Guardar como anotação
              </Button>
              <Button
                variante="secundario"
                disabled={decidir.isPending}
                onClick={() => decidir.mutate({ destino: 'DADO_SOLO', categoria: 'SOLO' })}
              >
                É dado de solo
              </Button>
              <Button
                variante="perigo"
                disabled={decidir.isPending}
                onClick={() => decidir.mutate({ destino: 'DESCARTADA' })}
              >
                Descartar
              </Button>
            </>
          ) : (
            <>
              <span className="rounded-sm bg-canopy-soft px-2 py-1 text-xs font-medium text-canopy">
                {DESTINO_CAMPO[m.destino]}
              </span>
              <Button
                variante="texto"
                disabled={decidir.isPending}
                onClick={() => decidir.mutate({ destino: 'CAIXA_DE_ENTRADA' })}
              >
                Voltar para a caixa de entrada
              </Button>
            </>
          )}
          <Button variante="texto" onClick={() => setEditandoNota((v) => !v)}>
            {m.nota ? 'Editar nota' : 'Adicionar nota'}
          </Button>
          <Button disabled={analisar.isPending} onClick={() => analisar.mutate()}>
            {analisar.isPending ? 'Analisando…' : m.analise_ia ? 'Analisar de novo' : 'Analisar com IA'}
          </Button>
        </div>
      </div>

      {editandoNota && (
        <form
          className="mt-3 flex flex-col gap-2"
          onSubmit={(e) => {
            e.preventDefault()
            decidir.mutate({ nota }, { onSuccess: () => setEditandoNota(false) })
          }}
        >
          <textarea
            className={inputClass}
            rows={2}
            value={nota}
            maxLength={2000}
            placeholder="Ex.: fica de anotação para o talhão Grão 4.0; conferir com o laudo"
            onChange={(e) => setNota(e.target.value)}
          />
          <div className="flex gap-2">
            <Button type="submit" disabled={decidir.isPending}>
              Salvar nota
            </Button>
            <Button variante="texto" onClick={() => setEditandoNota(false)}>
              Cancelar
            </Button>
          </div>
        </form>
      )}
      <div className="mt-2">
        <ErrorMessage>{erro && mensagemErro(erro)}</ErrorMessage>
      </div>
    </article>
  )
}

function Entrada({ talhoes }) {
  const queryClient = useQueryClient()
  const [texto, setTexto] = useState('')
  const [remetente, setRemetente] = useState('')
  const enviar = useMutation({
    mutationFn: criarMensagem,
    onSuccess: () => {
      setTexto('')
      queryClient.invalidateQueries({ queryKey: ['campo'] })
    },
  })
  return (
    <Panel titulo="Simular mensagem do WhatsApp">
      <p className="mb-3 text-sm text-muted">
        Etapa de teste: digite como se fosse o agrônomo. Quando o WhatsApp estiver conectado, as mensagens
        chegarão aqui sozinhas, já classificadas.
      </p>
      <form
        className="grid gap-3 md:grid-cols-[1fr_200px]"
        onSubmit={(e) => {
          e.preventDefault()
          if (texto.trim()) enviar.mutate({ texto, remetente: remetente || undefined })
        }}
      >
        <Field label="Mensagem">
          <textarea
            className={inputClass}
            rows={3}
            maxLength={4000}
            value={texto}
            onChange={(e) => setTexto(e.target.value)}
            placeholder={`Ex.: Coletei solo no ${talhoes[0]?.nome ?? 'Grão 4.0'}, pH deu 5,1 e P baixo`}
          />
        </Field>
        <div className="flex flex-col gap-3">
          <Field label="Quem enviou (opcional)">
            <input
              className={inputClass}
              value={remetente}
              maxLength={80}
              onChange={(e) => setRemetente(e.target.value)}
              placeholder="Nome do agrônomo"
            />
          </Field>
          <Button type="submit" disabled={enviar.isPending || !texto.trim()} className="mt-auto">
            {enviar.isPending ? 'Classificando…' : 'Enviar mensagem de teste'}
          </Button>
        </div>
      </form>
      <div className="mt-2">
        <ErrorMessage>{enviar.error && mensagemErro(enviar.error)}</ErrorMessage>
      </div>
    </Panel>
  )
}

export default function CadernoDeCampo() {
  const [categoria, setCategoria] = useState('')
  const [destino, setDestino] = useState('CAIXA_DE_ENTRADA')

  const { data: resumo } = useQuery({ queryKey: ['campo', 'resumo'], queryFn: resumoCampo })
  const { data: talhoes = [] } = useQuery({
    queryKey: ['talhoes', 'todos'],
    queryFn: () => listarTalhoes({ size: 200 }).then((r) => r.items),
  })
  const {
    data: mensagens,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['campo', 'mensagens', categoria, destino],
    queryFn: () => listarMensagens({ categoria: categoria || undefined, destino: destino || undefined }),
  })

  return (
    <>
      <PageHeader
        titulo="Caderno de campo"
        descricao="Mensagens informais do agrônomo, separadas por assunto. Você decide o que fazer com cada uma."
      />

      <div className="grid grid-cols-[minmax(0,1fr)] gap-6 lg:grid-cols-[230px_minmax(0,1fr)]">
        <nav aria-label="Categorias" className="min-w-0 lg:sticky lg:top-4 lg:self-start">
          <ul className="flex gap-2 overflow-x-auto lg:flex-col lg:overflow-visible">
            {[
              { categoria: '', total: resumo?.total, pendentes: resumo?.pendentes },
              ...(resumo?.categorias ?? []),
            ].map((c) => (
              <li key={c.categoria || 'todas'}>
                <button
                  type="button"
                  onClick={() => setCategoria(c.categoria)}
                  aria-pressed={categoria === c.categoria}
                  className={`flex w-full items-center justify-between gap-3 whitespace-nowrap rounded-md border px-3 py-2 text-left text-sm ${
                    categoria === c.categoria
                      ? 'border-canopy bg-canopy-soft font-medium text-canopy'
                      : 'border-line bg-panel hover:border-canopy'
                  }`}
                >
                  <span>{c.categoria ? CATEGORIA_CAMPO[c.categoria] : 'Todas as categorias'}</span>
                  <span className="flex items-center gap-1.5">
                    {c.pendentes > 0 && (
                      <span
                        title="Na caixa de entrada"
                        className="rounded-full bg-straw px-1.5 text-xs font-semibold text-[#1f2a24]"
                      >
                        {c.pendentes}
                      </span>
                    )}
                    <span className="text-xs text-muted tabular">{c.total ?? 0}</span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </nav>

        <div className="min-w-0 space-y-4">
          <Entrada talhoes={talhoes} />

          <div
            role="tablist"
            className="sem-barra flex gap-1 overflow-x-auto overflow-y-hidden border-b border-line"
          >
            {ABAS.map((aba) => (
              <button
                key={aba.id || 'todas'}
                role="tab"
                type="button"
                aria-selected={destino === aba.id}
                onClick={() => setDestino(aba.id)}
                className={`-mb-px whitespace-nowrap border-b-2 px-4 py-2 text-sm font-medium ${
                  destino === aba.id
                    ? 'border-canopy text-canopy'
                    : 'border-transparent text-muted hover:text-ink'
                }`}
              >
                {aba.rotulo}
              </button>
            ))}
          </div>

          <ErrorMessage>{error && mensagemErro(error)}</ErrorMessage>
          {isLoading ? (
            <Loading />
          ) : mensagens?.length ? (
            mensagens.map((m) => <Cartao key={m.id} mensagem={m} talhoes={talhoes} />)
          ) : (
            <EmptyState titulo="Nenhuma mensagem aqui">
              Envie uma mensagem de teste acima ou troque de aba e de categoria.
            </EmptyState>
          )}
        </div>
      </div>
    </>
  )
}
