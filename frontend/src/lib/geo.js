/** "POLYGON((lon lat, lon lat, ...))" → [[lat, lon], ...] para o Leaflet. */
export function wktParaLatLng(wkt) {
  const miolo = /POLYGON\s*\(\((.+?)\)/i.exec(wkt ?? '')?.[1]
  if (!miolo) return null
  return miolo.split(',').map((par) => {
    const [lon, lat] = par.trim().split(/\s+/).map(Number)
    return [lat, lon]
  })
}
