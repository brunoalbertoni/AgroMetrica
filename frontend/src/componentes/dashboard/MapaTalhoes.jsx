import { MapContainer, Polygon, Popup, TileLayer, Tooltip } from 'react-leaflet'
import { Link } from 'react-router-dom'

import { COR_SEVERIDADE, SEVERIDADE, SISTEMA, numero } from '../../compartilhado/format'
import { wktParaLatLng } from '../../compartilhado/geo'

const SEM_ALERTA = '#e3eee4'

const centro = (pontos) => [
  pontos.reduce((soma, p) => soma + p[0], 0) / pontos.length,
  pontos.reduce((soma, p) => soma + p[1], 0) / pontos.length,
]

/** Rótulo do lado oposto ao do talhão vizinho mais próximo, para nomes de vizinhos não se sobreporem. */
function posicoesDosRotulos(poligonos) {
  const centros = poligonos.map((t) => ({ id: t.id, c: centro(t.pontos) }))
  return new Map(
    centros.map(({ id, c }) => {
      const vizinhos = centros.filter((o) => o.id !== id)
      if (vizinhos.length === 0) return [id, { direcao: 'center', offset: [0, 0] }]
      const k = Math.cos((c[0] * Math.PI) / 180)
      const dist = (o) => Math.hypot(o.c[0] - c[0], (o.c[1] - c[1]) * k)
      const perto = vizinhos.reduce((a, b) => (dist(a) <= dist(b) ? a : b))
      const dy = perto.c[0] - c[0]
      const dx = (perto.c[1] - c[1]) * k
      if (Math.abs(dy) >= Math.abs(dx))
        return [id, dy > 0 ? { direcao: 'bottom', offset: [0, 12] } : { direcao: 'top', offset: [0, -12] }]
      return [id, dx > 0 ? { direcao: 'left', offset: [-12, 0] } : { direcao: 'right', offset: [12, 0] }]
    }),
  )
}

/** Mapa dos talhões pintados pela severidade do alerta aberto mais grave. */
export default function MapaTalhoes({ talhoes, altura = 360 }) {
  const poligonos = talhoes.map((t) => ({ ...t, pontos: wktParaLatLng(t.geometria) })).filter((t) => t.pontos)

  const rotulos = posicoesDosRotulos(poligonos)

  if (poligonos.length === 0) {
    return (
      <p
        className="flex items-center justify-center rounded bg-paper text-sm text-muted"
        style={{ height: altura }}
      >
        Nenhum talhão tem geometria cadastrada.
      </p>
    )
  }

  const todos = poligonos.flatMap((t) => t.pontos)
  const lats = todos.map((p) => p[0])
  const lons = todos.map((p) => p[1])
  const limites = [
    [Math.min(...lats), Math.min(...lons)],
    [Math.max(...lats), Math.max(...lons)],
  ]

  return (
    <div>
      <div className="overflow-hidden rounded border border-line" style={{ height: altura }}>
        <MapContainer
          bounds={limites}
          boundsOptions={{ padding: [24, 24] }}
          scrollWheelZoom={false}
          style={{ height: '100%' }}
        >
          <TileLayer
            attribution="Imagem &copy; Esri, Maxar, Earthstar Geographics"
            url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
          />
          {poligonos.map((t) => (
            <Polygon
              key={t.id}
              positions={t.pontos}
              pathOptions={{
                color: '#ffffff',
                weight: 2,
                fillColor: COR_SEVERIDADE[t.severidade] ?? SEM_ALERTA,
                fillOpacity: t.severidade ? 0.7 : 0.45,
              }}
            >
              <Tooltip
                direction={rotulos.get(t.id).direcao}
                offset={rotulos.get(t.id).offset}
                permanent
                className="!border-0 !bg-transparent !shadow-none"
              >
                <span className="font-display text-sm font-semibold text-white [text-shadow:0_1px_3px_#000]">
                  {t.nome}
                </span>
              </Tooltip>
              <Popup>
                <p className="font-display text-base font-semibold">{t.nome}</p>
                <p>
                  {SISTEMA[t.sistema]} · {numero(t.area_ha, 2)} ha
                </p>
                <p>Último NDVI: {numero(t.ultimo_ndvi, 2)}</p>
                <p>Alerta: {t.severidade ? SEVERIDADE[t.severidade] : 'nenhum'}</p>
                <Link to={`/talhoes/${t.id}`}>Abrir talhão</Link>
              </Popup>
            </Polygon>
          ))}
        </MapContainer>
      </div>
      <ul className="mt-2 flex flex-wrap gap-4 text-xs text-muted" aria-label="Legenda do mapa">
        <li className="flex items-center gap-1.5">
          <span className="h-3 w-3 rounded-sm" style={{ background: COR_SEVERIDADE.ALTA }} /> Alerta de dano
          (alta)
        </li>
        <li className="flex items-center gap-1.5">
          <span className="h-3 w-3 rounded-sm" style={{ background: COR_SEVERIDADE.MEDIA }} /> Alerta de
          atenção (média)
        </li>
        <li className="flex items-center gap-1.5">
          <span className="h-3 w-3 rounded-sm border border-line" style={{ background: SEM_ALERTA }} /> Sem
          alerta aberto
        </li>
      </ul>
    </div>
  )
}
