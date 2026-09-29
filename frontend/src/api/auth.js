import client from './client'

export const login = (email, senha) => client.post('/auth/login', { email, senha }).then((r) => r.data)
export const me = () => client.get('/auth/me').then((r) => r.data)
