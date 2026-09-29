import client from './client'

export const listarUsuarios = () => client.get('/usuarios').then((r) => r.data)
export const criarUsuario = (dados) => client.post('/usuarios', dados).then((r) => r.data)
export const atualizarUsuario = (id, dados) => client.patch(`/usuarios/${id}`, dados).then((r) => r.data)
export const removerUsuario = (id) => client.delete(`/usuarios/${id}`)
