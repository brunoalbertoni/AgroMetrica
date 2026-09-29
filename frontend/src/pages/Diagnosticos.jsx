import { useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { mensagemErro } from '../api/client'
import { listarDiagnosticos } from '../api/diagnosticos'
import { listarTalhoes } from '../api/talhoes'
import DataTable from '../components/DataTable'
import { ErrorMessage, Field, Loading, PageHeader, SeverityBadge, inputClass } from '../components/ui'
import { TIPO_DIAGNOSTICO, dataHora } from '../lib/format'

export default function Diagnosticos() {
  const navigate = useNavigate()
  const [filtros, setFiltros] = useState({ talhao_id: '', severidade: '', tipo: '' })
  const params = Object.fromEntries(Object.entries(filtros).filter(([, v]) => v))
  const {
    data: diags,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['diagnosticos', params],
    queryFn: () => listarDiagnosticos(params),
  })
  const { data: talhoes } = useQuery({
    queryKey: ['talhoes', 'todos'],
    queryFn: () => listarTalhoes({ size: 200 }),
  })

  const colunas = useMemo(
    () => [
      {
        accessorKey: 'criado_em',
        header: 'Data',
        cell: ({ getValue }) => <span className="tabular">{dataHora(getValue())}</span>,
      },
      {
        accessorKey: 'severidade',
        header: 'Severidade',
        cell: ({ getValue }) => <SeverityBadge severidade={getValue()} />,
      },
      { accessorKey: 'tipo', header: 'Tipo', cell: ({ getValue }) => TIPO_DIAGNOSTICO[getValue()] },
      { accessorKey: 'talhao_nome', header: 'Talhão' },
      { accessorKey: 'resumo', header: 'Resumo', enableSorting: false },
    ],
    [],
  )
  const campo = (nome) => (e) => setFiltros((f) => ({ ...f, [nome]: e.target.value }))

  return (
    <>
      <PageHeader
        titulo="Diagnósticos"
        descricao="Tudo o que o motor de regras e as armadilhas encontraram, do mais recente ao mais antigo."
      />
      <div className="mb-4 grid gap-3 sm:grid-cols-3">
        <Field label="Talhão">
          <select value={filtros.talhao_id} onChange={campo('talhao_id')} className={inputClass}>
            <option value="">Todos</option>
            {talhoes?.items.map((t) => (
              <option key={t.id} value={t.id}>
                {t.nome}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Severidade">
          <select value={filtros.severidade} onChange={campo('severidade')} className={inputClass}>
            <option value="">Todas</option>
            <option value="ALTA">Alta</option>
            <option value="MEDIA">Média</option>
            <option value="BAIXA">Baixa</option>
          </select>
        </Field>
        <Field label="Tipo">
          <select value={filtros.tipo} onChange={campo('tipo')} className={inputClass}>
            <option value="">Todos</option>
            {Object.entries(TIPO_DIAGNOSTICO).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
        </Field>
      </div>
      <ErrorMessage>{error && mensagemErro(error)}</ErrorMessage>
      {isLoading ? (
        <Loading />
      ) : (
        <DataTable
          colunas={colunas}
          dados={diags}
          onLinha={(d) => navigate(`/diagnosticos/${d.id}`)}
          vazio="Nenhum diagnóstico com esses filtros."
        />
      )}
    </>
  )
}
