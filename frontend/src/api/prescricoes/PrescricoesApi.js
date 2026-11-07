import client from '../../compartilhado/client'

export const alterarPrescricao = (id, status) =>
  client.patch(`/prescricoes/${id}`, { status }).then((r) => r.data)
