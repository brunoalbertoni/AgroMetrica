import client from '../../compartilhado/client'

export const resumoCampo = () => client.get('/campo/resumo').then((r) => r.data)
export const listarMensagens = (params) => client.get('/campo/mensagens', { params }).then((r) => r.data)
export const criarMensagem = (dados) => client.post('/campo/mensagens', dados).then((r) => r.data)
export const decidirMensagem = (id, dados) =>
  client.patch(`/campo/mensagens/${id}`, dados).then((r) => r.data)
export const analisarMensagem = (id) =>
  client.post(`/campo/mensagens/${id}/analisar`, null, { timeout: 60000 }).then((r) => r.data)
