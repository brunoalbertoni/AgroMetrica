import { useSyncExternalStore } from 'react'

/**
 * Tema da interface: 'sistema' (acompanha o sistema operacional), 'claro' ou 'escuro'.
 * A escolha fica no localStorage e vira o atributo <html data-theme="light|dark">, que o CSS usa
 * para trocar a paleta. O script de index.html aplica o mesmo atributo antes da primeira pintura.
 */
const CHAVE = 'agrometrica.tema'
export const OPCOES_TEMA = ['sistema', 'claro', 'escuro']

const consulta = window.matchMedia('(prefers-color-scheme: dark)')
const ouvintes = new Set()

function lerPreferencia() {
  try {
    const salvo = localStorage.getItem(CHAVE)
    return OPCOES_TEMA.includes(salvo) ? salvo : 'sistema'
  } catch {
    return 'sistema'
  }
}

const ehEscuro = (preferencia) => preferencia === 'escuro' || (preferencia === 'sistema' && consulta.matches)

function aplicar() {
  document.documentElement.dataset.theme = ehEscuro(lerPreferencia()) ? 'dark' : 'light'
  ouvintes.forEach((avisar) => avisar())
}

export function definirTema(preferencia) {
  try {
    localStorage.setItem(CHAVE, preferencia)
  } catch {
    /* sem armazenamento (janela privada): vale só até recarregar */
  }
  aplicar()
}

/** Chamar uma vez ao iniciar o app: aplica o tema e acompanha mudanças do sistema operacional. */
export function iniciarTema() {
  aplicar()
  consulta.addEventListener('change', () => {
    if (lerPreferencia() === 'sistema') aplicar()
  })
}

function assinar(avisar) {
  ouvintes.add(avisar)
  return () => ouvintes.delete(avisar)
}

export function useTema() {
  const preferencia = useSyncExternalStore(assinar, lerPreferencia, () => 'sistema')
  return { preferencia, escuro: ehEscuro(preferencia), definir: definirTema }
}
