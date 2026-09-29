import { Suspense, lazy } from 'react'
import { Route, Routes } from 'react-router-dom'

import Layout from '../components/Layout'
import { EmptyState, Loading } from '../components/ui'
import Login from '../pages/Login'
import PrivateRoute from './PrivateRoute'
import RoleRoute from './RoleRoute'

const Comparativo = lazy(() => import('../pages/Comparativo'))
const Dashboard = lazy(() => import('../pages/Dashboard'))
const DiagnosticoDetalhe = lazy(() => import('../pages/DiagnosticoDetalhe'))
const Diagnosticos = lazy(() => import('../pages/Diagnosticos'))
const Pragas = lazy(() => import('../pages/Pragas'))
const Produtos = lazy(() => import('../pages/Produtos'))
const TalhaoDetalhe = lazy(() => import('../pages/TalhaoDetalhe'))
const Talhoes = lazy(() => import('../pages/Talhoes'))
const Upload = lazy(() => import('../pages/Upload'))
const Usuarios = lazy(() => import('../pages/Usuarios'))

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
