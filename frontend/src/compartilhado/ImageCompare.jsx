import { useId, useState } from 'react'

/**
 * Comparador original × processada com divisória arrastável.
 * `rotulo` nomeia o índice da processada: "índice RGB (VARI)" em fotos, "NDVI" em GeoTIFF.
 */
export default function ImageCompare({ original, processada, rotulo = 'Processada', alt = '' }) {
  const [posicao, setPosicao] = useState(50)
  const id = useId()

  if (!processada) {
    return <img src={original} alt={alt} className="block h-auto w-full rounded" />
  }

  return (
    <figure>
      <div className="relative select-none overflow-hidden rounded">
        <img src={original} alt={alt} className="block h-auto w-full" />
        <img
          src={processada}
          alt={`${alt} (${rotulo})`}
          className="absolute inset-0 h-full w-full object-cover"
          style={{ clipPath: `inset(0 0 0 ${posicao}%)` }}
        />
        <div
          className="pointer-events-none absolute inset-y-0 w-0.5 bg-white shadow"
          style={{ left: `${posicao}%` }}
        />
        <span className="absolute left-2 top-2 rounded-sm bg-ink/75 px-2 py-0.5 text-xs text-white">
          Original
        </span>
        <span className="absolute right-2 top-2 rounded-sm bg-ink/75 px-2 py-0.5 text-xs text-white">
          {rotulo}
        </span>
      </div>
      <label htmlFor={id} className="sr-only">
        Posição da divisória entre original e {rotulo}
      </label>
      <input
        id={id}
        type="range"
        min={0}
        max={100}
        value={posicao}
        onChange={(e) => setPosicao(Number(e.target.value))}
        className="mt-2 w-full accent-canopy"
      />
    </figure>
  )
}
