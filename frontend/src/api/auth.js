import api from './index'

export function login(username, password) {
  return api.post('/auth/login', { username, password }).then((r) => r.data)
}

export function getMe() {
  return api.get('/auth/me').then((r) => r.data)
}

export function updateProfile(data) {
  return api.put('/auth/profile', data).then((r) => r.data)
}

export function changePassword(old_password, new_password) {
  return api.put('/auth/change-password', { old_password, new_password }).then((r) => r.data)
}
