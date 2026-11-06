import { useCallback, useEffect, useRef } from 'react'

/**
 * Imagem com as caixas de detecção desenhadas num <canvas> sobreposto.
 * As caixas vêm normalizadas (0–1) e são escaladas pelo tamanho exibido na tela,
 * então continuam alinhadas em qualquer largura.
 */
export default function BBoxCanvas({ src, caixas = [], alt, cor = '#c2362b' }) {
  const imgRef = useRef(null)
  const canvasRef = useRef(null)

  const desenhar = useCallback(() => {
    const img = imgRef.current
    const canvas = canvasRef.current
    if (!img || !canvas || !img.complete) return
    const largura = img.clientWidth
    const altura = img.clientHeight
    const dpr = window.devicePixelRatio || 1
    canvas.width = Math.round(largura * dpr)
    canvas.height = Math.round(altura * dpr)
    canvas.style.width = `${largura}px`
    canvas.style.height = `${altura}px`
    const ctx = canvas.getContext('2d')
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    ctx.clearRect(0, 0, largura, altura)
    ctx.lineWidth = 2
    ctx.font = '600 11px "Public Sans", sans-serif'
    caixas.forEach((c, i) => {
      const x = c.x * largura
      const y = c.y * altura
      const w = c.w * largura
      const h = c.h * altura
      ctx.strokeStyle = '#ffffff'
      ctx.lineWidth = 4
      ctx.strokeRect(x, y, w, h)
      ctx.strokeStyle = cor
      ctx.lineWidth = 2
      ctx.strokeRect(x, y, w, h)
      const texto = c.confianca ? `${i + 1} · ${Math.round(c.confianca * 100)}%` : String(i + 1)
      const tw = ctx.measureText(texto).width + 8
      const ty = y > 16 ? y - 16 : y + h
      ctx.fillStyle = cor
      ctx.fillRect(x, ty, tw, 16)
      ctx.fillStyle = '#ffffff'
      ctx.fillText(texto, x + 4, ty + 12)
    })
  }, [caixas, cor])

  useEffect(() => {
    const img = imgRef.current
    if (!img) return
    const observador = new ResizeObserver(desenhar)
    observador.observe(img)
    desenhar()
    return () => observador.disconnect()
  }, [desenhar])

  return (
    <figure>
      <div className="relative inline-block w-full">
        <img ref={imgRef} src={src} alt={alt} onLoad={desenhar} className="block h-auto w-full rounded" />
        <canvas ref={canvasRef} className="pointer-events-none absolute left-0 top-0" aria-hidden />
      </div>
      <figcaption className="mt-2 text-sm text-muted">
        {caixas.length === 0
          ? 'Nenhuma detecção marcada nesta imagem.'
          : `${caixas.length} ${caixas.length === 1 ? 'detecção marcada' : 'detecções marcadas'}.`}
      </figcaption>
    </figure>
  )
}
