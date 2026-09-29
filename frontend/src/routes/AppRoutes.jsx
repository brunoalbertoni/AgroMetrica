import { Route, Routes } from 'react-router-dom'

import Layout from '../components/Layout'
import { EmptyState } from '../components/ui'
import Login from '../pages/Login'
import Talhoes from '../pages/Talhoes'
import Usuarios from '../pages/Usuarios'
import PrivateRoute from './PrivateRoute'
import RoleRoute from './RoleRoute'

export default function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<PrivateRoute />}>
        <Route element={<Layout />}>
          <Route path="/" element={<Talhoes />} />
          <Route path="/talhoes" element={<Talhoes />} />
          <Route element={<RoleRoute perfis={['ADMIN']} />}>
            <Route path="/usuarios" element={<Usuarios />} />
          </Route>
          <Route path="*" element={<EmptyState titulo="Página não encontrada">Confira o endereço ou use o menu.</EmptyState>} />
        </Route>
      </Route>
    </Routes>
  )
}
