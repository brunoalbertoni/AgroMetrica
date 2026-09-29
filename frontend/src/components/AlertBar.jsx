import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { listarAlertas, marcarLido } from '../api/alertas'
import { dataCurta } from '../lib/format'

const TOM = {
  ALTA: { faixa: 'bg-alarm text-white', ponto: 'bg-alarm', rotulo: 'dano' },
  MEDIA: { faixa: 'bg-straw text-ink', ponto: 'bg-straw', rotulo: 'atenção' },
}

/** Faixa de alertas não lidos. Atualiza a cada 60 s. Vermelho = ALTA, amarelo = MÉDIA. */
export default function AlertBar() {
  const [aberta, setAberta] = useState(false)
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { data: alertas = [] } = useQuery({
    queryKey: ['alertas', { lido: false }],
    queryFn: () => listarAlertas({ lido: false }),
    refetchInterval: 60_000,
  })
  const lido = useMutation({
    mutationFn: marcarLido,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['alertas'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
    },
  })

  if (alertas.length === 0) return null

  const altos = alertas.filter((a) => a.severidade === 'ALTA').length
  const tom = TOM[altos > 0 ? 'ALTA' : 'MEDIA']
  const principal = alertas[0]
  const abrir = (a) => {
    setAberta(false)
    navigate(`/talhoes/${a.talhao_id}?diagnostico=${a.diagnostico_id}`)
  }

  return (
    <div className="relative">
      <div className={`flex items-center gap-3 px-4 py-2 text-sm md:px-8 ${tom.faixa}`} role="status">
        <span className="font-display text-lg font-semibold tabular whitespace-nowrap">
          {alertas.length} {alertas.length === 1 ? 'alerta' : 'alertas'}
        </span>
        <button
          type="button"
          onClick={() => abrir(principal)}
          className="min-w-0 flex-1 truncate text-left underline-offset-2 hover:underline"
        >
          {principal.mensagem}
        </button>
        <button
          type="button"
          onClick={() => setAberta((v) => !v)}
          aria-expanded={aberta}
          className="whitespace-nowrap rounded border border-current/40 px-2 py-0.5 text-xs font-medium hover:bg-white/15"
        >
          {aberta ? 'Fechar lista' : 'Ver todos'}
        </button>
      </div>

      {aberta && (
        <ul className="absolute inset-x-0 top-full z-[1100] max-h-[60vh] overflow-y-auto border-b border-line bg-panel shadow-lg md:left-8 md:right-auto md:w-[640px] md:rounded-b-md md:border-x">
          {alertas.map((a) => (
            <li key={a.id} className="flex items-start gap-3 border-b border-line px-4 py-3 last:border-0">
              <span className={`mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full ${TOM[a.severidade]?.ponto}`} aria-hidden />
              <button type="button" onClick={() => abrir(a)} className="min-w-0 flex-1 text-left text-sm hover:text-canopy">
                <span className="block">{a.mensagem}</span>
                <span className="text-xs text-muted">
                  {dataCurta(a.criado_em)} · nível de {TOM[a.severidade]?.rotulo}
                </span>
              </button>
              <button
                type="button"
                onClick={() => lido.mutate(a.id)}
                disabled={lido.isPending}
                className="whitespace-nowrap text-xs font-medium text-muted hover:text-canopy"
              >
                Marcar como lido
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
