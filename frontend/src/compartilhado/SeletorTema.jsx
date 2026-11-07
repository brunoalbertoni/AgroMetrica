import { useTema } from './tema'

const ICONES = {
  claro: (
    <path
      d="M12 4V2m0 20v-2m8-8h2M2 12h2m13.66-5.66 1.41-1.41M4.93 19.07l1.41-1.41m0-11.32L4.93 4.93m14.14 14.14-1.41-1.41M12 7.5a4.5 4.5 0 1 0 0 9 4.5 4.5 0 0 0 0-9Z"
      strokeLinecap="round"
    />
  ),
  sistema: <path d="M3 5h18v11H3zM8 20h8M12 16v4" strokeLinecap="round" strokeLinejoin="round" />,
  escuro: <path d="M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5Z" strokeLinejoin="round" />,
}
const ROTULOS = { claro: 'Tema claro', sistema: 'Tema do sistema', escuro: 'Tema escuro' }
const ORDEM = ['claro', 'sistema', 'escuro']

/**
 * Escolha do tema (claro, do sistema, escuro).
 * variante "menu": sobre o fundo verde do menu; "pagina": sobre o fundo da página.
 */
export default function SeletorTema({ variante = 'menu', className = '' }) {
  const { preferencia, definir } = useTema()
  const trilho = variante === 'menu' ? 'bg-white/10' : 'bg-line/60'
  const ativo = variante === 'menu' ? 'bg-white text-canopy-dark' : 'bg-panel text-ink shadow-sm'
  const inativo = variante === 'menu' ? 'text-white/70 hover:text-white' : 'text-muted hover:text-ink'
  return (
    <div
      role="group"
      aria-label="Tema da interface"
      className={`inline-flex rounded-full p-0.5 ${trilho} ${className}`}
    >
      {ORDEM.map((opcao) => (
        <button
          key={opcao}
          type="button"
          onClick={() => definir(opcao)}
          aria-pressed={preferencia === opcao}
          aria-label={ROTULOS[opcao]}
          title={ROTULOS[opcao]}
          className={`flex h-7 w-7 items-center justify-center rounded-full transition-colors ${
            preferencia === opcao ? ativo : inativo
          }`}
        >
          <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
            {ICONES[opcao]}
          </svg>
        </button>
      ))}
    </div>
  )
}
