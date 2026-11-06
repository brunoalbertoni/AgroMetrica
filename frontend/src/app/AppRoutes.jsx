import { Suspense, lazy } from 'react'
import { Route, Routes } from 'react-router-dom'

import Layout from './Layout'
import { EmptyState, Loading } from '../compartilhado/ui'
import Login from '../paginas/auth/Login'
import PrivateRoute from './PrivateRoute'
import RoleRoute from './RoleRoute'

const Comparativo = lazy(() => import('../paginas/dashboard/Comparativo'))
const Dashboard = lazy(() => import('../paginas/dashboard/Dashboard'))
const DiagnosticoDetalhe = lazy(() => import('../paginas/diagnosticos/DiagnosticoDetalhe'))
const Diagnosticos = lazy(() => import('../paginas/diagnosticos/Diagnosticos'))
const Pragas = lazy(() => import('../paginas/pragas/Pragas'))
const Produtos = lazy(() => import('../paginas/produtos/Produtos'))
const TalhaoDetalhe = lazy(() => import('../paginas/talhoes/TalhaoDetalhe'))
const Talhoes = lazy(() => import('../paginas/talhoes/Talhoes'))
const Upload = lazy(() => import('../paginas/uploads/Upload'))
const Usuarios = lazy(() => import('../paginas/usuarios/Usuarios'))

export default function AppRoutes() {
  return (
    <Suspense fallback={<Loading />}>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route element={<PrivateRoute />}>
          <Route element={<Layout />}>
            <Route path="/" element={<Dashboard />} />
            <Route path="/talhoes" element={<Talhoes />} />
            <Route path="/talhoes/:id" element={<TalhaoDetalhe />} />
            <Route path="/upload" element={<Upload />} />
            <Route path="/diagnosticos" element={<Diagnosticos />} />
            <Route path="/diagnosticos/:id" element={<DiagnosticoDetalhe />} />
            <Route path="/produtos" element={<Produtos />} />
            <Route path="/pragas" element={<Pragas />} />
            <Route path="/comparativo" element={<Comparativo />} />
            <Route element={<RoleRoute perfis={['ADMIN']} />}>
              <Route path="/usuarios" element={<Usuarios />} />
            </Route>
            <Route
              path="*"
              element={
                <EmptyState titulo="Página não encontrada">Confira o endereço ou use o menu.</EmptyState>
              }
            />
          </Route>
        </Route>
      </Routes>
    </Suspense>
  )
}
