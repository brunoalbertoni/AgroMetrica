import client from './client'

export const listarPragas = () => client.get('/pragas').then((r) => r.data)
export const criarPraga = (dados) => client.post('/pragas', dados).then((r) => r.data)
export const atualizarPraga = (id, dados) => client.patch(`/pragas/${id}`, dados).then((r) => r.data)
export const removerPraga = (id) => client.delete(`/pragas/${id}`)
