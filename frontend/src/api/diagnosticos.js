import client from './client'

export const listarDiagnosticos = (params) => client.get('/diagnosticos', { params }).then((r) => r.data)
export const obterDiagnostico = (id) => client.get(`/diagnosticos/${id}`).then((r) => r.data)
export const rodarDiagnostico = (talhaoId) => client.post(`/diagnosticos/rodar/${talhaoId}`).then((r) => r.data)
