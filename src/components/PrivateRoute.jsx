import React from 'react'
import { Navigate } from 'react-router-dom'
import auth from '../services/auth'

const PrivateRoute = ({ children, requireAdmin = false }) => {
  const isAuthenticated = auth.isAuthenticated()
  const isAdmin = auth.isAdmin()

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  if (requireAdmin && !isAdmin) {
    return <Navigate to="/" replace />
  }

  return children
}

export default PrivateRoute