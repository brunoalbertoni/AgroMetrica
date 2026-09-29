import { Link, useParams } from 'react-router-dom'

import DiagnosticoPainel from '../components/DiagnosticoPainel'
import { Panel } from '../components/ui'

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
