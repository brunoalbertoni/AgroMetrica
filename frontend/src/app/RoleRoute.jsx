import { Outlet } from 'react-router-dom'

import { EmptyState } from '../compartilhado/ui'
import { useAuth } from '../stores/auth/AuthContext'

/** Restringe a rota a perfis. ADMIN sempre passa. */
export default function RoleRoute({ perfis }) {
  const { usuario } = useAuth()
  if (usuario?.perfil !== 'ADMIN' && !perfis.includes(usuario?.perfil)) {
    return (
      <EmptyState titulo="Acesso restrito">
        Esta área é só para administradores. Peça acesso a quem gerencia o sistema.
      </EmptyState>
    )
  }
  return <Outlet />
}
