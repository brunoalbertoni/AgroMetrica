import client from './client'

export const listarAlertas = (params) => client.get('/alertas', { params }).then((r) => r.data)
export const marcarLido = (id) => client.patch(`/alertas/${id}/lido`).then((r) => r.data)
