const num = (casas) =>
  new Intl.NumberFormat('pt-BR', { minimumFractionDigits: casas, maximumFractionDigits: casas })

export function numero(valor, casas = 0) {
  if (valor === null || valor === undefined || Number.isNaN(Number(valor))) return '—'
  return num(casas).format(Number(valor))
}

/** Número com até 2 casas, sem zeros à direita (100 e 0,75). */
export function numeroCurto(valor) {
  if (valor === null || valor === undefined || Number.isNaN(Number(valor))) return '—'
  return new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 2 }).format(Number(valor))
}

/** Datas ISO "2024-01-05" ou "2024-01-05T08:00:00" sem conversão de fuso. */
function partes(iso) {
  if (!iso) return null
  const [d, h] = String(iso).split('T')
  const [ano, mes, dia] = d.split('-').map(Number)
  const [hora, minuto] = (h || '00:00').split(':').map(Number)
  return { ano, mes, dia, hora, minuto }
}

export function data(iso) {
  const p = partes(iso)
  if (!p) return '—'
  return `${String(p.dia).padStart(2, '0')}/${String(p.mes).padStart(2, '0')}/${p.ano}`
}

export function dataCurta(iso) {
  const p = partes(iso)
  if (!p) return ''
  return `${String(p.dia).padStart(2, '0')}/${String(p.mes).padStart(2, '0')}`
}

export function dataHora(iso) {
  const p = partes(iso)
  if (!p) return '—'
  return `${data(iso)} ${String(p.hora).padStart(2, '0')}:${String(p.minuto).padStart(2, '0')}`
}

export const SISTEMA = { AGRO_4_0: 'Agro 4.0', CONVENCIONAL: 'Convencional' }
export const FINALIDADE = { GRAO: 'Grão', SILAGEM: 'Silagem' }
export const SEVERIDADE = { ALTA: 'Alta', MEDIA: 'Média', BAIXA: 'Baixa' }
export const TIPO_DIAGNOSTICO = {
  PRAGA: 'Praga',
  VIGOR: 'Vigor',
  NUTRICIONAL: 'Nutricional',
  HIDRICO: 'Hídrico',
}
export const STATUS_PRESCRICAO = {
  SUGERIDA: 'Sugerida',
  APROVADA: 'Aprovada',
  APLICADA: 'Aplicada',
  DESCARTADA: 'Descartada',
}
export const CLASSE_PRODUTO = {
  INSETICIDA: 'Inseticida',
  FUNGICIDA: 'Fungicida',
  HERBICIDA: 'Herbicida',
  FERTILIZANTE: 'Fertilizante',
  CORRETIVO: 'Corretivo',
  SEMENTE: 'Semente',
}
export const PERFIL = { ADMIN: 'Administrador', AGRONOMO: 'Agrônomo' }

/** Cor de série por sistema (validada para daltonismo); silagem usa linha tracejada. */
export const COR_SISTEMA = { AGRO_4_0: 'var(--color-serie-40)', CONVENCIONAL: 'var(--color-serie-conv)' }
export const COR_SEVERIDADE = { ALTA: '#c2362b', MEDIA: '#d9a21b', BAIXA: '#5d6b62' }

export const CATEGORIA_CAMPO = {
  SOLO: 'Solo',
  PRAGA: 'Pragas e doenças',
  CLIMA: 'Clima',
  MANEJO: 'Manejo',
  OBSERVACAO: 'Observações',
  OUTROS: 'Outros',
}
/** Cores (fundo e texto) de cada categoria, usando os tokens do tema claro e escuro. */
export const COR_CATEGORIA_CAMPO = {
  SOLO: 'bg-straw-soft text-straw-text',
  PRAGA: 'bg-alarm-soft text-alarm',
  CLIMA: 'bg-serie-conv-soft text-serie-conv',
  MANEJO: 'bg-canopy-soft text-canopy',
  OBSERVACAO: 'bg-line/60 text-ink',
  OUTROS: 'bg-line/60 text-muted',
}
export const DESTINO_CAMPO = {
  CAIXA_DE_ENTRADA: 'Caixa de entrada',
  ANOTACAO: 'Anotação',
  DADO_SOLO: 'Dado de solo',
  DESCARTADA: 'Descartada',
}
