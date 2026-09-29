import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState } from 'react'

import { mensagemErro } from '../api/client'
import { listarPragas } from '../api/pragas'
import { atualizarProduto, criarProduto, listarProdutos, removerProduto } from '../api/produtos'
import DataTable from '../components/DataTable'
import { Button, ErrorMessage, Field, Loading, Modal, PageHeader, inputClass } from '../components/ui'
import { useAuth } from '../context/AuthContext'
import { CLASSE_PRODUTO, numeroCurto } from '../lib/format'

const VAZIO = {
  nome_comercial: '',
  ingrediente_ativo: '',
  classe: 'INSETICIDA',
  dose_min: '',
  dose_max: '',
  unidade: 'mL/ha',
  carencia_dias: '',
  registro_mapa: '',
  praga_ids: [],
}

function FormProduto({ inicial, pragas, onSalvar, salvando, erro }) {
  const [form, setForm] = useState(inicial)
  const campo = (nome) => (e) => setForm((f) => ({ ...f, [nome]: e.target.value }))
  const alternarPraga = (id) =>
    setForm((f) => ({
      ...f,
      praga_ids: f.praga_ids.includes(id) ? f.praga_ids.filter((x) => x !== id) : [...f.praga_ids, id],
    }))

  return (
    <form
      className="space-y-4"
      onSubmit={(e) => {
        e.preventDefault()
        onSalvar({
          nome_comercial: form.nome_comercial,
          ingrediente_ativo: form.ingrediente_ativo || null,
          classe: form.classe,
          dose_min: Number(form.dose_min),
          dose_max: Number(form.dose_max),
          unidade: form.unidade,
          carencia_dias:
            form.carencia_dias === '' || form.carencia_dias === null ? null : Number(form.carencia_dias),
          registro_mapa: form.registro_mapa || null,
          praga_ids: form.praga_ids,
        })
      }}
    >
      <Field label="Nome comercial">
        <input
          required
          value={form.nome_comercial}
          onChange={campo('nome_comercial')}
          className={inputClass}
        />
      </Field>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Ingrediente ativo">
          <input
            value={form.ingrediente_ativo ?? ''}
            onChange={campo('ingrediente_ativo')}
            className={inputClass}
          />
        </Field>
        <Field label="Classe">
          <select value={form.classe} onChange={campo('classe')} className={inputClass}>
            {Object.entries(CLASSE_PRODUTO).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
        </Field>
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        <Field label="Dose mínima">
          <input
            required
            type="number"
            min="0"
            step="any"
            value={form.dose_min}
            onChange={campo('dose_min')}
            className={inputClass}
          />
        </Field>
        <Field label="Dose máxima">
          <input
            required
            type="number"
            min="0"
            step="any"
            value={form.dose_max}
            onChange={campo('dose_max')}
            className={inputClass}
          />
        </Field>
        <Field label="Unidade">
          <input required value={form.unidade} onChange={campo('unidade')} className={inputClass} />
        </Field>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Carência (dias)">
          <input
            type="number"
            min="0"
            value={form.carencia_dias ?? ''}
            onChange={campo('carencia_dias')}
            className={inputClass}
          />
        </Field>
        <Field label="Registro no MAPA">
          <input value={form.registro_mapa ?? ''} onChange={campo('registro_mapa')} className={inputClass} />
        </Field>
      </div>
      <fieldset>
        <legend className="mb-1 text-sm font-medium">Pragas-alvo</legend>
        <p className="mb-2 text-xs text-muted">
          O produto passa a ser sugerido nas prescrições dessas pragas.
        </p>
        <div className="flex flex-wrap gap-2">
          {pragas.map((p) => (
            <label
              key={p.id}
              className="flex items-center gap-2 rounded border border-line px-2.5 py-1.5 text-sm"
            >
              <input
                type="checkbox"
                checked={form.praga_ids.includes(p.id)}
                onChange={() => alternarPraga(p.id)}
                className="accent-canopy"
              />
              {p.nome}
            </label>
          ))}
        </div>
      </fieldset>
      <ErrorMessage>{erro}</ErrorMessage>
      <div className="flex justify-end">
        <Button type="submit" disabled={salvando}>
          {inicial.id ? 'Salvar alterações' : 'Cadastrar produto'}
        </Button>
      </div>
    </form>
  )
}

export default function Produtos() {
  const { isAdmin } = useAuth()
  const queryClient = useQueryClient()
  const [editando, setEditando] = useState(null)
  const { data: produtos, isLoading, error } = useQuery({ queryKey: ['produtos'], queryFn: listarProdutos })
  const { data: pragas = [] } = useQuery({ queryKey: ['pragas'], queryFn: listarPragas })
  const nomePraga = useMemo(() => Object.fromEntries(pragas.map((p) => [p.id, p.nome])), [pragas])

  const salvar = useMutation({
    mutationFn: (dados) => (editando.id ? atualizarProduto(editando.id, dados) : criarProduto(dados)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['produtos'] })
      setEditando(null)
    },
  })
  const remover = useMutation({
    mutationFn: removerProduto,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['produtos'] }),
  })

  const colunas = useMemo(() => {
    const base = [
      {
        accessorKey: 'nome_comercial',
        header: 'Produto',
        cell: ({ getValue }) => <span className="font-medium">{getValue()}</span>,
      },
      { accessorKey: 'ingrediente_ativo', header: 'Ingrediente ativo' },
      { accessorKey: 'classe', header: 'Classe', cell: ({ getValue }) => CLASSE_PRODUTO[getValue()] },
      {
        id: 'dose',
        header: 'Dose',
        enableSorting: false,
        cell: ({ row }) => (
          <span className="whitespace-nowrap tabular">
            {numeroCurto(row.original.dose_min)}–{numeroCurto(row.original.dose_max)} {row.original.unidade}
          </span>
        ),
      },
      {
        accessorKey: 'carencia_dias',
        header: 'Carência',
        cell: ({ getValue }) => (getValue() != null ? `${getValue()} dias` : '—'),
      },
      {
        id: 'pragas',
        header: 'Pragas-alvo',
        enableSorting: false,
        cell: ({ row }) => row.original.praga_ids.map((id) => nomePraga[id]).join(', ') || '—',
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
                window.confirm(`Excluir ${row.original.nome_comercial}?`) && remover.mutate(row.original.id)
              }
            >
              Excluir
            </Button>
          </div>
        ),
      },
    ]
  }, [isAdmin, nomePraga, remover])

  return (
    <>
      <PageHeader
        titulo="Produtos"
        descricao={
          isAdmin
            ? 'Catálogo usado nas prescrições. A dose sugerida é a média entre a mínima e a máxima.'
            : 'Catálogo usado nas prescrições. Só administradores podem editar.'
        }
      >
        {isAdmin && <Button onClick={() => setEditando(VAZIO)}>Cadastrar produto</Button>}
      </PageHeader>
      <ErrorMessage>{(error || remover.error) && mensagemErro(error || remover.error)}</ErrorMessage>
      {isLoading ? (
        <Loading />
      ) : (
        <DataTable colunas={colunas} dados={produtos} vazio="Nenhum produto cadastrado." />
      )}
      <Modal
        aberto={Boolean(editando)}
        titulo={editando?.id ? 'Editar produto' : 'Cadastrar produto'}
        onFechar={() => {
          setEditando(null)
          salvar.reset()
        }}
      >
        {editando && (
          <FormProduto
            key={editando.id ?? 'novo'}
            inicial={editando}
            pragas={pragas}
            onSalvar={salvar.mutate}
            salvando={salvar.isPending}
            erro={salvar.error && mensagemErro(salvar.error)}
          />
        )}
      </Modal>
    </>
  )
}
