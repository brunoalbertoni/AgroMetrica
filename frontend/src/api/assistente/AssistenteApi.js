import client from '../../compartilhado/client'

export const conversar = (mensagem, historico) =>
  client.post('/assistente/chat', { mensagem, historico }, { timeout: 60000 }).then((r) => r.data.resposta)
