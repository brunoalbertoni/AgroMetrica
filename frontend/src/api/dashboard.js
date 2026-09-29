import client from './client'

export const resumoDashboard = () => client.get('/dashboard/resumo').then((r) => r.data)
export const comparativo = (a, b) => client.get('/comparativo', { params: { a, b } }).then((r) => r.data)
