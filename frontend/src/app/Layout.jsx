import { NavLink, Outlet } from 'react-router-dom'

import { useAuth } from '../stores/auth/AuthContext'
import SeletorTema from '../compartilhado/SeletorTema'
import { PERFIL } from '../compartilhado/format'
import AlertBar from '../componentes/alertas/AlertBar'
import AssistentePainel from '../componentes/assistente/AssistentePainel'

const LINKS = [
  { to: '/', rotulo: 'Painel', end: true },
  { to: '/talhoes', rotulo: 'Talhões' },
  { to: '/diagnosticos', rotulo: 'Diagnósticos' },
  { to: '/comparativo', rotulo: '4.0 × Convencional' },
  { to: '/upload', rotulo: 'Enviar dados' },
  { to: '/pragas', rotulo: 'Pragas' },
  { to: '/produtos', rotulo: 'Produtos' },
  { to: '/usuarios', rotulo: 'Usuários', admin: true },
]

function Marca() {
  return (
    <div className="flex items-center gap-2">
      <svg viewBox="0 0 32 32" className="h-8 w-8" aria-hidden>
        <rect width="32" height="32" rx="7" fill="#f6f7f2" />
        <path
          d="M16 26V11M16 17c-4 0-7-3-7-7 4 0 7 3 7 7zm0-2c3.5 0 6-2.5 6-6-3.5 0-6 2.5-6 6z"
          stroke="#2f6b3f"
          strokeWidth="2"
          fill="none"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      <span className="font-display text-2xl font-semibold tracking-tight text-white">AgroMétrica</span>
    </div>
  )
}

export default function Layout() {
  const { usuario, sair, isAdmin } = useAuth()
  const links = LINKS.filter((l) => !l.admin || isAdmin)

  return (
    <div className="min-h-screen md:grid md:grid-cols-[232px_1fr]">
      <aside className="bg-canopy-dark text-white md:sticky md:top-0 md:flex md:h-screen md:flex-col">
        <div className="flex items-center justify-between px-5 py-4 md:py-6">
          <Marca />
          <div className="flex items-center gap-3 md:hidden">
            <SeletorTema />
            <button type="button" onClick={sair} className="text-sm text-white/80 hover:text-white">
              Sair
            </button>
          </div>
        </div>
        <nav className="sem-barra flex gap-1 overflow-x-auto px-3 pb-3 md:flex-1 md:flex-col md:overflow-visible md:pb-0">
          {links.map((l) => (
            <NavLink
              key={l.to}
              to={l.to}
              end={l.end}
              className={({ isActive }) =>
                `whitespace-nowrap rounded px-3 py-2 text-sm font-medium ${
                  isActive ? 'bg-panel text-canopy' : 'text-white/85 hover:bg-white/10 hover:text-white'
                }`
              }
            >
              {l.rotulo}
            </NavLink>
          ))}
        </nav>
        <div className="hidden border-t border-white/15 px-5 py-4 text-sm md:block">
          <p className="font-medium">{usuario?.nome}</p>
          <p className="text-white/70">Perfil: {PERFIL[usuario?.perfil]}</p>
          <div className="mt-3">
            <SeletorTema />
          </div>
          <button
            type="button"
            onClick={sair}
            className="mt-2 text-white/80 underline-offset-2 hover:text-white hover:underline"
          >
            Sair
          </button>
        </div>
      </aside>

      <div className="isolate min-w-0">
        <AlertBar />
        <main className="mx-auto max-w-[1280px] px-4 pb-28 pt-6 md:px-8 md:pb-28 md:pt-8">
          <Outlet />
        </main>
      </div>
      <AssistentePainel />
    </div>
  )
}
