import { Link, useParams } from 'react-router-dom'

import DiagnosticoPainel from '../../componentes/diagnosticos/DiagnosticoPainel'
import { Panel } from '../../compartilhado/ui'

export default function DiagnosticoDetalhe() {
  const { id } = useParams()
  return (
    <>
      <nav className="mb-4 text-sm text-muted">
        <Link to="/diagnosticos" className="hover:text-canopy">
          Diagnósticos
        </Link>{' '}
        / nº {id}
      </nav>
      <Panel>
        <DiagnosticoPainel id={Number(id)} />
      </Panel>
    </>
  )
}
