import client from './client'

export const listarTalhoes = (params) => client.get('/talhoes', { params }).then((r) => r.data)
export const obterTalhao = (id) => client.get(`/talhoes/${id}`).then((r) => r.data)
export const metricasTalhao = (id, params) => client.get(`/talhoes/${id}/metricas`, { params }).then((r) => r.data)
export const soloTalhao = (id) => client.get(`/talhoes/${id}/solo`).then((r) => r.data)
