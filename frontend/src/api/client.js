import axios from 'axios'

export const API_URL = import.meta.env.VITE_API_URL || (import.meta.env.DEV ? 'http://localhost:8000' : '')

export const apiClient = axios.create({
  baseURL: API_URL
})

export const buildApiUrl = (path = '') => {
  if (!path) return API_URL
  return `${API_URL}${path.startsWith('/') ? path : `/${path}`}`
}
