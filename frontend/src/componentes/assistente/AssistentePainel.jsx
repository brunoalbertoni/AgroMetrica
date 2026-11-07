import { useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

import { conversar } from '../../api/assistente/AssistenteApi'
import { mensagemErro } from '../../compartilhado/client'
import PainelVisual from './PainelVisual'

const AVATAR = '/assistente.svg'
const NOME = 'Assistente AgroMétrica'
const SUGESTOES = [
  'Compare o Grão 4.0 com o Grão Convecional',
  'Mostre as armadilhas com mais pragas',
  'Como está o NDVI dos talhões?',
]

const componentes = {
  table: (props) => (
    <div className="my-2 overflow-x-auto rounded border border-line">
      <table className="w-full border-collapse text-left text-[13px]" {...props} />
    </div>
  ),
  th: (props) => <th className="border border-line bg-paper px-2 py-1.5 font-semibold" {...props} />,
  td: (props) => <td className="border border-line px-2 py-1.5 align-top" {...props} />,
  p: (props) => <p className="my-1.5 first:mt-0 last:mb-0" {...props} />,
  ul: (props) => <ul className="my-1.5 list-disc space-y-0.5 pl-5" {...props} />,
  ol: (props) => <ol className="my-1.5 list-decimal space-y-0.5 pl-5" {...props} />,
  h1: (props) => <h3 className="mb-1 mt-3 text-base font-semibold" {...props} />,
  h2: (props) => <h3 className="mb-1 mt-3 text-base font-semibold" {...props} />,
  h3: (props) => <h4 className="mb-1 mt-2 text-[15px] font-semibold" {...props} />,
  strong: (props) => <strong className="font-semibold" {...props} />,
  a: (props) => <a className="text-canopy underline" target="_blank" rel="noreferrer" {...props} />,
}

function Avatar({ className = 'h-10 w-10' }) {
  return <img src={AVATAR} alt="" className={`${className} shrink-0 rounded-full`} />
}

function Mensagem({ m, onVerPainel }) {
  if (m.papel === 'usuario') {
    return (
      <div className="ml-auto max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-sm bg-canopy-soft px-3.5 py-2 text-sm text-ink">
        {m.texto}
      </div>
    )
  }
  return (
    <div className="flex items-start gap-2.5">
      <Avatar />
      <div className={`min-w-0 flex-1 pt-1 text-sm ${m.erro ? 'text-alarm' : 'text-ink'}`}>
        {m.erro ? (
          m.texto
        ) : (
          <ReactMarkdown remarkPlugins={[remarkGfm]} components={componentes}>
            {m.texto}
          </ReactMarkdown>
        )}
        {m.paineis?.length > 0 && (
          <button
            type="button"
            onClick={() => onVerPainel(m.paineis)}
            className="mt-2 inline-flex items-center gap-1.5 rounded-full border border-canopy/40 px-3 py-1 text-xs font-medium text-canopy hover:bg-canopy-soft"
          >
            <span aria-hidden>▦</span> Ver visualização{m.paineis.length > 1 ? ` (${m.paineis.length})` : ''}
          </button>
        )}
      </div>
    </div>
  )
}

export default function AssistentePainel() {
  const [aberto, setAberto] = useState(false)
  const [mensagens, setMensagens] = useState([])
  const [texto, setTexto] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [visual, setVisual] = useState(null) // { paineis, indice } do painel ao lado do chat
  const fimRef = useRef(null)

  useEffect(() => {
    fimRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [mensagens, enviando, aberto])

  async function enviar(conteudoEnviado) {
    const conteudo = (conteudoEnviado ?? texto).trim()
    if (!conteudo || enviando) return
    const historico = mensagens
      .filter((m) => !m.erro)
      .slice(-10)
      .map((m) => ({ papel: m.papel, texto: m.texto }))
    setMensagens((m) => [...m, { papel: 'usuario', texto: conteudo }])
    setTexto('')
    setEnviando(true)
    try {
      const { resposta, paineis = [] } = await conversar(conteudo, historico)
      setMensagens((m) => [...m, { papel: 'modelo', texto: resposta, paineis }])
      if (paineis.length > 0) setVisual({ paineis, indice: 0 })
    } catch (erro) {
      setMensagens((m) => [...m, { papel: 'modelo', texto: mensagemErro(erro), erro: true }])
    } finally {
      setEnviando(false)
    }
  }

  function aoTeclar(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      enviar()
    }
  }

  return (
    <>
      {!aberto && (
        <button
          type="button"
          onClick={() => setAberto(true)}
          aria-label="Abrir o assistente"
          title={NOME}
          className="fixed bottom-6 right-6 z-40 h-16 w-16 overflow-hidden rounded-full shadow-lg ring-4 ring-white transition hover:scale-105 hover:shadow-xl"
        >
          <img src={AVATAR} alt="" className="h-full w-full" />
        </button>
      )}

      {aberto && visual && (
        <PainelVisual
          paineis={visual.paineis}
          indice={visual.indice}
          onTrocar={(indice) => setVisual({ ...visual, indice })}
          onFechar={() => setVisual(null)}
        />
      )}

      {aberto && (
        <aside
          role="dialog"
          aria-label={NOME}
          className="fixed bottom-4 right-0 top-4 z-50 flex w-[calc(100%-1rem)] flex-col overflow-hidden rounded-l-xl border border-r-0 border-line bg-white shadow-2xl md:w-[440px]"
        >
          <header className="flex items-center justify-between border-b border-line px-4 py-3">
            <div className="flex items-center gap-2.5">
              <Avatar className="h-8 w-8" />
              <h2 className="font-sans text-[15px] font-semibold text-ink">{NOME}</h2>
            </div>
            <div className="flex items-center gap-1 text-muted">
              <button
                type="button"
                onClick={() => {
                  setMensagens([])
                  setVisual(null)
                }}
                disabled={mensagens.length === 0}
                aria-label="Limpar conversa"
                title="Limpar conversa"
                className="rounded p-1.5 hover:bg-paper hover:text-ink disabled:opacity-40"
              >
                <svg
                  viewBox="0 0 24 24"
                  className="h-5 w-5"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.8"
                >
                  <path
                    d="M4 7h16M10 11v6M14 11v6M6 7l1 12a2 2 0 002 2h6a2 2 0 002-2l1-12M9 7V4h6v3"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </button>
              <button
                type="button"
                onClick={() => setAberto(false)}
                aria-label="Fechar"
                title="Fechar"
                className="rounded p-1.5 hover:bg-paper hover:text-ink"
              >
                <svg
                  viewBox="0 0 24 24"
                  className="h-6 w-6"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                >
                  <path d="M6 6l12 12M18 6L6 18" strokeLinecap="round" />
                </svg>
              </button>
            </div>
          </header>

          <div className="flex-1 overflow-y-auto px-4 py-4">
            <div className="flex flex-col gap-4">
              <Mensagem
                m={{
                  papel: 'modelo',
                  texto:
                    'Olá! Sou o assistente do AgroMétrica. Posso consultar os talhões, NDVI, clima, solo, alertas, diagnósticos, pragas e produtos cadastrados. O que você quer saber?',
                }}
              />
              {mensagens.length === 0 && (
                <div className="flex flex-wrap gap-2 pl-[50px]">
                  {SUGESTOES.map((s) => (
                    <button
                      key={s}
                      type="button"
                      onClick={() => enviar(s)}
                      className="rounded-full border border-line px-3 py-1.5 text-left text-[13px] text-canopy-dark hover:bg-canopy-soft"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              )}
              {mensagens.map((m, i) => (
                <Mensagem key={i} m={m} onVerPainel={(paineis) => setVisual({ paineis, indice: 0 })} />
              ))}
              {enviando && (
                <div className="flex items-center gap-2.5">
                  <Avatar />
                  <div className="flex gap-1 pt-1" aria-label="Pensando">
                    {[0, 1, 2].map((i) => (
                      <span
                        key={i}
                        className="h-2 w-2 animate-bounce rounded-full bg-muted/60"
                        style={{ animationDelay: `${i * 0.15}s` }}
                      />
                    ))}
                  </div>
                </div>
              )}
              <div ref={fimRef} />
            </div>
          </div>

          <div className="border-t border-line p-4">
            <div className="flex items-end gap-2 rounded-lg border border-line px-3 py-2 focus-within:border-canopy focus-within:ring-2 focus-within:ring-canopy/20">
              <textarea
                value={texto}
                onChange={(e) => setTexto(e.target.value)}
                onKeyDown={aoTeclar}
                rows={1}
                maxLength={2000}
                placeholder="Escreva uma mensagem..."
                className="max-h-32 min-h-[28px] flex-1 resize-none bg-transparent py-1 text-sm focus:outline-none"
              />
              <button
                type="button"
                onClick={() => enviar()}
                disabled={enviando || !texto.trim()}
                aria-label="Enviar"
                className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-canopy text-white hover:bg-canopy-dark disabled:opacity-40"
              >
                <svg viewBox="0 0 24 24" className="h-5 w-5" fill="currentColor">
                  <path d="M3.4 20.4l17.45-7.48a1 1 0 000-1.84L3.4 3.6a.993.993 0 00-1.39.91L2 9.12c0 .5.37.93.87.99L17 12 2.87 13.88c-.5.07-.87.5-.87 1l.01 4.61c0 .71.73 1.2 1.39.91z" />
                </svg>
              </button>
            </div>
          </div>
        </aside>
      )}
    </>
  )
}
