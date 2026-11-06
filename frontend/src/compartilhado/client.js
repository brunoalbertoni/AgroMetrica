import axios from 'axios'

export const TOKEN_KEY = 'agrometrica.token'
export const USUARIO_KEY = 'agrometrica.usuario'

const client = axios.create({ baseURL: '/api' })

client.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY)
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

client.interceptors.response.use(
  (resposta) => resposta,
  (erro) => {
    const naLogin = erro.config?.url?.includes('/auth/login')
    if (erro.response?.status === 401 && !naLogin) {
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem(USUARIO_KEY)
      if (window.location.pathname !== '/login') window.location.assign('/login')
    }
    return Promise.reject(erro)
  },
)

/** Mensagem legível a partir do formato padrão da API: {"detail": "..."} */
export function mensagemErro(erro, padrao = 'Não foi possível concluir a operação.') {
  const detail = erro?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (!erro?.response) return 'Sem conexão com a API. Verifique se o backend está rodando.'
  return padrao
}

export default client
