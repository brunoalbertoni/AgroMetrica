import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState } from 'react'

import { mensagemErro } from '../api/client'
import { atualizarUsuario, criarUsuario, listarUsuarios, removerUsuario } from '../api/usuarios'
import DataTable from '../components/DataTable'
import { Button, ErrorMessage, Field, Loading, Modal, PageHeader, inputClass } from '../components/ui'
import { useAuth } from '../context/AuthContext'
import { PERFIL, data } from '../lib/format'

const VAZIO = { nome: '', email: '', senha: '', perfil: 'AGRONOMO', ativo: true }

function FormUsuario({ inicial, onSalvar, salvando, erro }) {
  const [form, setForm] = useState(inicial)
  const novo = !inicial.id
  const campo = (nome) => (e) =>
    setForm((f) => ({ ...f, [nome]: e.target.type === 'checkbox' ? e.target.checked : e.target.value }))

  return (
    <form
      className="space-y-4"
      onSubmit={(e) => {
        e.preventDefault()
        const { id: _id, criado_em: _c, ...dados } = form
        if (!novo && !dados.senha) delete dados.senha
        onSalvar(dados)
      }}
    >
      <Field label="Nome">
        <input required value={form.nome} onChange={campo('nome')} className={inputClass} />
      </Field>
      <Field label="E-mail">
        <input required type="email" value={form.email} onChange={campo('email')} className={inputClass} />
      </Field>
      <Field
        label={novo ? 'Senha' : 'Nova senha'}
        dica={novo ? 'Mínimo de 6 caracteres.' : 'Deixe em branco para manter a atual.'}
      >
        <input
          type="password"
          required={novo}
          minLength={6}
          value={form.senha ?? ''}
          onChange={campo('senha')}
          className={inputClass}
          autoComplete="new-password"
        />
      </Field>
      <Field label="Perfil">
        <select value={form.perfil} onChange={campo('perfil')} className={inputClass}>
          <option value="AGRONOMO">Agrônomo</option>
          <option value="ADMIN">Administrador</option>
        </select>
      </Field>
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={form.ativo}
          onChange={campo('ativo')}
          className="h-4 w-4 accent-canopy"
        />
        Pode entrar no sistema
      </label>
      <ErrorMessage>{erro}</ErrorMessage>
      <div className="flex justify-end">
        <Button type="submit" disabled={salvando}>
          {novo ? 'Cadastrar usuário' : 'Salvar alterações'}
        </Button>
      </div>
    </form>
  )
}

export default function Usuarios() {
  const { usuario: eu } = useAuth()
  const queryClient = useQueryClient()
  const [editando, setEditando] = useState(null)
  const { data: usuarios, isLoading, error } = useQuery({ queryKey: ['usuarios'], queryFn: listarUsuarios })

  const salvar = useMutation({
    mutationFn: (dados) => (editando.id ? atualizarUsuario(editando.id, dados) : criarUsuario(dados)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['usuarios'] })
      setEditando(null)
    },
  })
  const remover = useMutation({
    mutationFn: removerUsuario,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['usuarios'] }),
  })

  const colunas = useMemo(
    () => [
      { accessorKey: 'nome', header: 'Nome' },
      { accessorKey: 'email', header: 'E-mail' },
      { accessorKey: 'perfil', header: 'Perfil', cell: ({ getValue }) => PERFIL[getValue()] },
      {
        accessorKey: 'ativo',
        header: 'Situação',
        cell: ({ getValue }) => (getValue() ? 'Ativo' : <span className="text-muted">Bloqueado</span>),
      },
      { accessorKey: 'criado_em', header: 'Desde', cell: ({ getValue }) => data(getValue()) },
      {
        id: 'acoes',
        header: '',
        enableSorting: false,
        cell: ({ row }) => (
          <div className="flex justify-end gap-3">
            <Button variante="texto" onClick={() => setEditando({ ...row.original, senha: '' })}>
              Editar
            </Button>
            {row.original.id !== eu?.id && (
              <Button
                variante="texto"
                className="text-alarm"
                onClick={() => {
                  if (window.confirm(`Excluir ${row.original.nome}? Esta ação não pode ser desfeita.`)) {
                    remover.mutate(row.original.id)
                  }
                }}
              >
                Excluir
              </Button>
            )}
          </div>
        ),
      },
    ],
    [eu?.id, remover],
  )

  return (
    <>
      <PageHeader titulo="Usuários" descricao="Quem pode entrar no sistema e com qual perfil.">
        <Button onClick={() => setEditando(VAZIO)}>Cadastrar usuário</Button>
      </PageHeader>
      <ErrorMessage>{(error || remover.error) && mensagemErro(error || remover.error)}</ErrorMessage>
      {isLoading ? <Loading /> : <DataTable colunas={colunas} dados={usuarios} />}
      <Modal
        aberto={Boolean(editando)}
        titulo={editando?.id ? 'Editar usuário' : 'Cadastrar usuário'}
        onFechar={() => {
          setEditando(null)
          salvar.reset()
        }}
      >
        {editando && (
          <FormUsuario
            key={editando.id ?? 'novo'}
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
