import client from './client'

export const listarProdutos = () => client.get('/produtos').then((r) => r.data)
export const criarProduto = (dados) => client.post('/produtos', dados).then((r) => r.data)
export const atualizarProduto = (id, dados) => client.patch(`/produtos/${id}`, dados).then((r) => r.data)
export const removerProduto = (id) => client.delete(`/produtos/${id}`)
