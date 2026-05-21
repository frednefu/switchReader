import api from './index'

export function getUsers(params) {
  return api.get('/users', { params }).then((r) => r.data)
}

export function getUser(id) {
  return api.get(`/users/${id}`).then((r) => r.data)
}

export function createUser(data) {
  return api.post('/users', data).then((r) => r.data)
}

export function updateUser(id, data) {
  return api.put(`/users/${id}`, data).then((r) => r.data)
}

export function deleteUser(id) {
  return api.delete(`/users/${id}`).then((r) => r.data)
}

export function resetUserPassword(id, new_password) {
  return api.put(`/users/${id}/reset-password`, { old_password: '', new_password }).then((r) => r.data)
}
