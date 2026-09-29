import client from './client'

export function enviarImagem({ arquivo, talhaoId, tipo }) {
  const dados = new FormData()
  dados.append('arquivo', arquivo)
  dados.append('talhao_id', talhaoId)
  dados.append('tipo', tipo)
  return client.post('/imagens', dados).then((r) => r.data)
}
export const obterImagem = (id) => client.get(`/imagens/${id}`).then((r) => r.data)
