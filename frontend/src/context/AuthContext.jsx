import { useQueryClient } from '@tanstack/react-query'
import { createContext, useCallback, useContext, useMemo, useState } from 'react'

import { login as apiLogin } from '../api/auth'
import { TOKEN_KEY, USUARIO_KEY } from '../api/client'

const AuthContext = createContext(null)

function lerUsuarioSalvo() {
  try {
    const salvo = localStorage.getItem(USUARIO_KEY)
    return salvo && localStorage.getItem(TOKEN_KEY) ? JSON.parse(salvo) : null
  } catch {
    return null
  }
}

export function AuthProvider({ children }) {
  const [usuario, setUsuario] = useState(lerUsuarioSalvo)
  const queryClient = useQueryClient()

  const entrar = useCallback(async (email, senha) => {
    const { access_token, usuario: u } = await apiLogin(email, senha)
    localStorage.setItem(TOKEN_KEY, access_token)
    localStorage.setItem(USUARIO_KEY, JSON.stringify(u))
    setUsuario(u)
    return u
  }, [])

  const sair = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USUARIO_KEY)
    queryClient.clear()
    setUsuario(null)
  }, [queryClient])

  const valor = useMemo(
    () => ({
      usuario,
      entrar,
      sair,
      isAdmin: usuario?.perfil === 'ADMIN',
      // ADMIN também pode tudo o que o agrônomo pode
      isAgronomo: usuario?.perfil === 'AGRONOMO' || usuario?.perfil === 'ADMIN',
    }),
    [usuario, entrar, sair],
  )

  return <AuthContext.Provider value={valor}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth precisa estar dentro de <AuthProvider>')
  return ctx
}
