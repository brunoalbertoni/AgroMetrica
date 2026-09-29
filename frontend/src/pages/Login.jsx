import { useState } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'

import { mensagemErro } from '../api/client'
import { Button, ErrorMessage, Field, inputClass } from '../components/ui'
import { useAuth } from '../context/AuthContext'

export default function Login() {
  const { usuario, entrar } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [senha, setSenha] = useState('')
  const [erro, setErro] = useState('')
  const [enviando, setEnviando] = useState(false)

  if (usuario) return <Navigate to={location.state?.de ?? '/'} replace />

  async function enviar(e) {
    e.preventDefault()
    setErro('')
    setEnviando(true)
    try {
      await entrar(email, senha)
      navigate(location.state?.de ?? '/', { replace: true })
    } catch (err) {
      setErro(mensagemErro(err, 'Não foi possível entrar.'))
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="grid min-h-screen md:grid-cols-[1.1fr_1fr]">
      <div className="relative hidden overflow-hidden bg-canopy-dark md:block" aria-hidden>
        {/* Linhas de plantio: faixas diagonais que lembram a lavoura vista do drone */}
        <svg className="absolute inset-0 h-full w-full" preserveAspectRatio="none" viewBox="0 0 400 600">
          {Array.from({ length: 34 }, (_, i) => (
            <line
              key={i}
              x1={-200 + i * 22}
              y1="620"
              x2={60 + i * 22}
              y2="-20"
              stroke={i % 7 === 3 ? '#d9a21b' : '#2f6b3f'}
              strokeWidth={i % 7 === 3 ? 3 : 6}
              strokeLinecap="round"
              opacity={i % 7 === 3 ? 0.9 : 0.8}
            />
          ))}
        </svg>
        <div className="absolute bottom-10 left-10 right-10 text-white">
          <p className="font-display text-5xl font-semibold leading-none">AgroMétrica</p>
          <p className="mt-3 max-w-sm text-white/80">
            NDVI, clima, solo e armadilhas de cada talhão em um só lugar, com o manejo 4.0 lado a lado com o
            convencional.
          </p>
        </div>
      </div>

      <div className="flex items-center justify-center px-6 py-12">
        <form onSubmit={enviar} className="w-full max-w-sm space-y-5">
          <div>
            <h1 className="text-3xl font-semibold">Entrar</h1>
            <p className="mt-1 text-sm text-muted">Use o e-mail e a senha cadastrados pelo administrador.</p>
          </div>
          <Field label="E-mail">
            <input
              type="email"
              autoComplete="username"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className={inputClass}
            />
          </Field>
          <Field label="Senha">
            <input
              type="password"
              autoComplete="current-password"
              required
              value={senha}
              onChange={(e) => setSenha(e.target.value)}
              className={inputClass}
            />
          </Field>
          <ErrorMessage>{erro}</ErrorMessage>
          <Button type="submit" className="w-full" disabled={enviando}>
            {enviando ? 'Entrando…' : 'Entrar'}
          </Button>
        </form>
      </div>
    </div>
  )
}
