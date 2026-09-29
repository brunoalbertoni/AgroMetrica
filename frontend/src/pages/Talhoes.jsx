import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { mensagemErro } from '../api/client'
import { listarTalhoes } from '../api/talhoes'
import DataTable from '../components/DataTable'
import { ErrorMessage, Field, PageHeader, SistemaTag, inputClass } from '../components/ui'
import { FINALIDADE, data, numero } from '../lib/format'

const TAMANHO = 10

function useDebounce(valor, ms = 350) {
  const [atrasado, setAtrasado] = useState(valor)
  useEffect(() => {
    const t = setTimeout(() => setAtrasado(valor), ms)
    return () => clearTimeout(t)
  }, [valor, ms])
  return atrasado
}

export default function Talhoes() {
  const navigate = useNavigate()
  const [page, setPage] = useState(1)
  const [sort, setSort] = useState('nome')
  const [busca, setBusca] = useState('')
  const [sistema, setSistema] = useState('')
  const [deficit, setDeficit] = useState('')
  const buscaAtrasada = useDebounce(busca)

  const params = {
    page,
    size: TAMANHO,
    sort: sort || undefined,
    busca: buscaAtrasada || undefined,
    sistema: sistema || undefined,
    deficit_min: deficit || undefined,
  }
  const { data: pagina, isLoading, error } = useQuery({
    queryKey: ['talhoes', params],
    queryFn: () => listarTalhoes(params),
    placeholderData: keepPreviousData,
  })

  const colunas = useMemo(
    () => [
      {
        accessorKey: 'nome',
        header: 'Talhão',
        cell: ({ row }) => (
          <Link to={`/talhoes/${row.original.id}`} className="font-medium text-ink hover:text-canopy" onClick={(e) => e.stopPropagation()}>
            {row.original.nome}
          </Link>
        ),
      },
      { accessorKey: 'sistema', header: 'Sistema', cell: ({ getValue }) => <SistemaTag sistema={getValue()} /> },
      { accessorKey: 'finalidade', header: 'Finalidade', cell: ({ getValue }) => FINALIDADE[getValue()] },
      { accessorKey: 'cultura', header: 'Cultura' },
      {
        accessorKey: 'area_ha',
        header: 'Área (ha)',
        meta: { alinhar: 'direita' },
        cell: ({ getValue }) => numero(getValue(), 2),
      },
      {
        id: 'ndvi',
        header: 'Último NDVI',
        enableSorting: false,
        meta: { alinhar: 'direita' },
        cell: ({ row }) => numero(row.original.ultima_metrica?.ndvi_medio, 2),
      },
      {
        id: 'balanco',
        header: 'Balanço hídrico',
        enableSorting: false,
        meta: { alinhar: 'direita' },
        cell: ({ row }) => {
          const v = row.original.ultima_metrica?.balanco_hidrico_mm
          if (v === null || v === undefined) return '—'
          return <span className={v < -25 ? 'font-semibold text-alarm' : ''}>{numero(v, 1)} mm</span>
        },
      },
      {
        id: 'data',
        header: 'Atualizado em',
        enableSorting: false,
        cell: ({ row }) => data(row.original.ultima_metrica?.data),
      },
    ],
    [],
  )

  const mudar = (setter) => (e) => {
    setter(e.target.value)
    setPage(1)
  }

  return (
    <>
      <PageHeader titulo="Talhões" descricao="Situação de cada talhão pela última leitura de NDVI e de balanço hídrico." />

      <div className="mb-4 grid gap-3 sm:grid-cols-[1fr_200px_200px]">
        <Field label="Buscar">
          <input
            type="search"
            placeholder="Nome ou cultura"
            value={busca}
            onChange={mudar(setBusca)}
            className={inputClass}
          />
        </Field>
        <Field label="Sistema">
          <select value={sistema} onChange={mudar(setSistema)} className={inputClass}>
            <option value="">Todos</option>
            <option value="AGRO_4_0">Agro 4.0</option>
            <option value="CONVENCIONAL">Convencional</option>
          </select>
        </Field>
        <Field label="Déficit hídrico">
          <select value={deficit} onChange={mudar(setDeficit)} className={inputClass}>
            <option value="">Qualquer</option>
            <option value="10">Pior que −10 mm</option>
            <option value="25">Pior que −25 mm</option>
            <option value="40">Pior que −40 mm</option>
          </select>
        </Field>
      </div>

      <ErrorMessage>{error && mensagemErro(error)}</ErrorMessage>
      {isLoading ? null : (
        <DataTable
          colunas={colunas}
          dados={pagina?.items}
          sort={sort}
          onSort={(s) => {
            setSort(s)
            setPage(1)
          }}
          paginacao={{ page, size: TAMANHO, total: pagina?.total ?? 0, onPage: setPage }}
          onLinha={(t) => navigate(`/talhoes/${t.id}`)}
          vazio="Nenhum talhão com esses filtros."
        />
      )}
    </>
  )
}
