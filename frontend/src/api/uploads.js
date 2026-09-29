import client from './client'

export function enviarPlanilha(tipo, arquivo) {
  const dados = new FormData()
  dados.append('arquivo', arquivo)
  return client.post(`/uploads/${tipo}`, dados).then((r) => r.data)
}
