import client from '../../compartilhado/client'

export const climaDiario = (params) =>
  client.get('/clima', { params: { agregacao: 'dia', ...params } }).then((r) => r.data)
