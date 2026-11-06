import { Navigate, Outlet, useLocation } from 'react-router-dom'

import { useAuth } from '../stores/auth/AuthContext'

export default function PrivateRoute() {
  const { usuario } = useAuth()
  const location = useLocation()
  if (!usuario) return <Navigate to="/login" replace state={{ de: location.pathname + location.search }} />
  return <Outlet />
}
