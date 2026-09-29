import { flexRender, getCoreRowModel, getSortedRowModel, useReactTable } from '@tanstack/react-table'
import { useState } from 'react'

/**
 * Tabela com TanStack Table.
 * - Paginação no servidor: passe `paginacao = { page, size, total, onPage }` e `sort/onSort`.
 * - Sem `paginacao`, ordena no cliente.
 */
export default function DataTable({
  colunas,
  dados,
  paginacao,
  sort,
  onSort,
  vazio = 'Nenhum registro.',
  onLinha,
}) {
  const servidor = Boolean(onSort)
  const [sortingLocal, setSortingLocal] = useState([])
  const sorting = servidor
    ? sort
      ? [{ id: sort.replace(/^-/, ''), desc: sort.startsWith('-') }]
      : []
    : sortingLocal

  // TanStack Table não é memoizável pelo React Compiler; o componente simplesmente não é otimizado.
  // eslint-disable-next-line react-hooks/incompatible-library
  const tabela = useReactTable({
    data: dados ?? [],
    columns: colunas,
    state: { sorting },
    manualSorting: servidor,
    onSortingChange: (atualizador) => {
      const novo = typeof atualizador === 'function' ? atualizador(sorting) : atualizador
      if (!servidor) return setSortingLocal(novo)
      onSort(novo[0] ? `${novo[0].desc ? '-' : ''}${novo[0].id}` : null)
    },
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: servidor ? undefined : getSortedRowModel(),
  })

  const paginas = paginacao ? Math.max(1, Math.ceil(paginacao.total / paginacao.size)) : 1

  return (
    <div className="overflow-hidden rounded-md border border-line bg-panel">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-line bg-paper text-muted">
            {tabela.getHeaderGroups().map((grupo) => (
              <tr key={grupo.id}>
                {grupo.headers.map((h) => {
                  const podeOrdenar = h.column.getCanSort()
                  const ordem = h.column.getIsSorted()
                  return (
                    <th
                      key={h.id}
                      scope="col"
                      className={`px-4 py-2.5 font-medium ${h.column.columnDef.meta?.alinhar === 'direita' ? 'text-right' : ''}`}
                      aria-sort={ordem === 'asc' ? 'ascending' : ordem === 'desc' ? 'descending' : undefined}
                    >
                      {podeOrdenar ? (
                        <button
                          type="button"
                          onClick={h.column.getToggleSortingHandler()}
                          className="inline-flex items-center gap-1 hover:text-ink"
                        >
                          {flexRender(h.column.columnDef.header, h.getContext())}
                          <span aria-hidden className="text-xs">
                            {ordem === 'asc' ? '▲' : ordem === 'desc' ? '▼' : '↕'}
                          </span>
                        </button>
                      ) : (
                        flexRender(h.column.columnDef.header, h.getContext())
                      )}
                    </th>
                  )
                })}
              </tr>
            ))}
          </thead>
          <tbody>
            {tabela.getRowModel().rows.length === 0 && (
              <tr>
                <td colSpan={colunas.length} className="px-4 py-8 text-center text-muted">
                  {vazio}
                </td>
              </tr>
            )}
            {tabela.getRowModel().rows.map((linha) => (
              <tr
                key={linha.id}
                onClick={onLinha ? () => onLinha(linha.original) : undefined}
                className={`border-b border-line last:border-0 ${onLinha ? 'cursor-pointer hover:bg-canopy-soft/50' : ''}`}
              >
                {linha.getVisibleCells().map((c) => (
                  <td
                    key={c.id}
                    className={`px-4 py-2.5 align-middle ${c.column.columnDef.meta?.alinhar === 'direita' ? 'text-right tabular' : ''}`}
                  >
                    {flexRender(c.column.columnDef.cell, c.getContext())}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {paginacao && (
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line px-4 py-2.5 text-sm text-muted">
          <span className="tabular">
            {paginacao.total === 0
              ? 'Nenhum resultado'
              : `${(paginacao.page - 1) * paginacao.size + 1}–${Math.min(paginacao.page * paginacao.size, paginacao.total)} de ${paginacao.total}`}
          </span>
          <div className="flex items-center gap-2">
            <button
              type="button"
              className="rounded border border-line px-2.5 py-1 hover:border-canopy disabled:opacity-40"
              disabled={paginacao.page <= 1}
              onClick={() => paginacao.onPage(paginacao.page - 1)}
            >
              Anterior
            </button>
            <span className="tabular">
              Página {paginacao.page} de {paginas}
            </span>
            <button
              type="button"
              className="rounded border border-line px-2.5 py-1 hover:border-canopy disabled:opacity-40"
              disabled={paginacao.page >= paginas}
              onClick={() => paginacao.onPage(paginacao.page + 1)}
            >
              Próxima
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
