import api from './index'

export function syncDepartments() {
  return api.post('/sys/departments/sync').then((r) => r.data)
}

export function getDepartmentTree(all = false) {
  return api.get('/sys/departments/tree', { params: { all } }).then((r) => r.data)
}

export function getDepartmentUsers(deptId) {
  return api.get(`/sys/departments/${deptId}/users`).then((r) => r.data)
}
