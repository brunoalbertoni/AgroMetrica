import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState } from 'react'

import { mensagemErro } from '../api/client'
import { atualizarPraga, criarPraga, listarPragas, removerPraga } from '../api/pragas'
import DataTable from '../components/DataTable'
import { Button, ErrorMessage, Field, Loading, Modal, PageHeader, inputClass } from '../components/ui'
import { useAuth } from '../context/AuthContext'
import { numero } from '../lib/format'

const VAZIO = {
  nome: '',
  nome_cientifico: '',
  cultura: 'Milho',
  limiar_alerta: '',
  limiar_controle: '',
  limiar_dano: '',
}

function FormPraga({ inicial, onSalvar, salvando, erro }) {
  const [form, setForm] = useState(inicial)
  const campo = (nome) => (e) => setForm((f) => ({ ...f, [nome]: e.target.value }))
  return (
    <form
      className="space-y-4"
      onSubmit={(e) => {
        e.preventDefault()
        onSalvar({
          nome: form.nome,
          nome_cientifico: form.nome_cientifico || null,
          cultura: form.cultura || null,
          limiar_alerta: Number(form.limiar_alerta),
          limiar_controle: Number(form.limiar_controle),
          limiar_dano: Number(form.limiar_dano),
        })
      }}
    >
      <Field label="Nome">
        <input required value={form.nome} onChange={campo('nome')} className={inputClass} />
      </Field>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Nome científico">
          <input
            value={form.nome_cientifico ?? ''}
            onChange={campo('nome_cientifico')}
            className={`${inputClass} italic`}
          />
        </Field>
        <Field label="Cultura">
          <input value={form.cultura ?? ''} onChange={campo('cultura')} className={inputClass} />
        </Field>
      </div>
      <fieldset>
        <legend className="mb-1 text-sm font-medium">Limiares (indivíduos por armadilha)</legend>
        <p className="mb-2 text-xs text-muted">
          Alerta gera diagnóstico de severidade baixa; controle, média; dano, alta.
        </p>
        <div className="grid gap-3 sm:grid-cols-3">
          {[
            ['limiar_alerta', 'Alerta'],
            ['limiar_controle', 'Controle'],
            ['limiar_dano', 'Dano'],
          ].map(([k, r]) => (
            <Field key={k} label={r}>
              <input
                required
                type="number"
                min="0"
                step="any"
                value={form[k]}
                onChange={campo(k)}
                className={inputClass}
              />
            </Field>
          ))}
        </div>
      </fieldset>
      <ErrorMessage>{erro}</ErrorMessage>
      <div className="flex justify-end">
        <Button type="submit" disabled={salvando}>
          {inicial.id ? 'Salvar alterações' : 'Cadastrar praga'}
        </Button>
      </div>
    </form>
  )
}

export default function Pragas() {
  const { isAdmin } = useAuth()
  const queryClient = useQueryClient()
  const [editando, setEditando] = useState(null)
  const { data: pragas, isLoading, error } = useQuery({ queryKey: ['pragas'], queryFn: listarPragas })
  const salvar = useMutation({
    mutationFn: (dados) => (editando.id ? atualizarPraga(editando.id, dados) : criarPraga(dados)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pragas'] })
      setEditando(null)
    },
  })
  const remover = useMutation({
    mutationFn: removerPraga,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['pragas'] }),
  })

  const colunas = useMemo(() => {
    const base = [
      {
        accessorKey: 'nome',
        header: 'Praga',
        cell: ({ getValue }) => <span className="font-medium">{getValue()}</span>,
      },
      {
        accessorKey: 'nome_cientifico',
        header: 'Nome científico',
        cell: ({ getValue }) => <i>{getValue() ?? '—'}</i>,
      },
      { accessorKey: 'cultura', header: 'Cultura' },
      {
        accessorKey: 'limiar_alerta',
        header: 'Alerta',
        meta: { alinhar: 'direita' },
        cell: ({ getValue }) => numero(getValue(), 0),
      },
      {
        accessorKey: 'limiar_controle',
        header: 'Controle',
        meta: { alinhar: 'direita' },
        cell: ({ getValue }) => numero(getValue(), 0),
      },
      {
        accessorKey: 'limiar_dano',
        header: 'Dano',
        meta: { alinhar: 'direita' },
        cell: ({ getValue }) => numero(getValue(), 0),
      },
    ]
    if (!isAdmin) return base
    return [
      ...base,
      {
        id: 'acoes',
        header: '',
        enableSorting: false,
        cell: ({ row }) => (
          <div className="flex justify-end gap-3">
            <Button variante="texto" onClick={() => setEditando(row.original)}>
              Editar
            </Button>
            <Button
              variante="texto"
              className="text-alarm"
              onClick={() =>
                window.confirm(`Excluir ${row.original.nome}?`) && remover.mutate(row.original.id)
              }
            >
              Excluir
            </Button>
          </div>
        ),
      },
    ]
  }, [isAdmin, remover])

  return (
    <>
      <PageHeader titulo="Pragas" descricao="Limiares usados para classificar as leituras das armadilhas.">
        {isAdmin && <Button onClick={() => setEditando(VAZIO)}>Cadastrar praga</Button>}
      </PageHeader>
      <ErrorMessage>{(error || remover.error) && mensagemErro(error || remover.error)}</ErrorMessage>
      {isLoading ? (
        <Loading />
      ) : (
        <DataTable colunas={colunas} dados={pragas} vazio="Nenhuma praga cadastrada." />
      )}
      <Modal
        aberto={Boolean(editando)}
        titulo={editando?.id ? 'Editar praga' : 'Cadastrar praga'}
        onFechar={() => {
          setEditando(null)
          salvar.reset()
        }}
      >
        {editando && (
          <FormPraga
            key={editando.id ?? 'nova'}
            inicial={editando}
            onSalvar={salvar.mutate}
            salvando={salvar.isPending}
            erro={salvar.error && mensagemErro(salvar.error)}
          />
        )}
      </Modal>
    </>
  )
}
