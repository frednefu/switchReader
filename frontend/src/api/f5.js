import api from './index'

export function getF5Devices(params) {
  return api.get('/f5', { params }).then((r) => r.data)
}

export function getF5Device(id) {
  return api.get(`/f5/${id}`).then((r) => r.data)
}

export function createF5Device(data) {
  return api.post('/f5', data).then((r) => r.data)
}

export function updateF5Device(id, data) {
  return api.put(`/f5/${id}`, data).then((r) => r.data)
}

export function deleteF5Device(id) {
  return api.delete(`/f5/${id}`).then((r) => r.data)
}

export function triggerF5Scan(id) {
  return api.post(`/f5/${id}/scan`).then((r) => r.data)
}

export function testF5Connection(data) {
  return api.post('/f5/test', data).then((r) => r.data)
}

export function scanAllF5Devices() {
  return api.post('/f5/scan-all').then((r) => r.data)
}

export function deleteAllF5Devices() {
  return api.delete('/f5/all').then((r) => r.data)
}

export function getF5VirtualServers(id, params) {
  return api.get(`/f5/${id}/virtual-servers`, { params }).then((r) => r.data)
}

export function getF5PoolMembers(id, params) {
  return api.get(`/f5/${id}/pool-members`, { params }).then((r) => r.data)
}

export function getF5Rules(id, params) {
  return api.get(`/f5/${id}/rules`, { params }).then((r) => r.data)
}

export function getF5ApplicationMap(id, params) {
  return api.get(`/f5/${id}/application-map`, { params }).then((r) => r.data)
}

export function exportF5VirtualServers(id, params) {
  return api.get(`/f5/${id}/virtual-servers/export`, { params, responseType: 'blob' }).then((r) => {
    const url = URL.createObjectURL(r.data)
    const a = document.createElement('a')
    a.href = url
    a.download = `f5_vs_${id}.xlsx`
    a.click()
    URL.revokeObjectURL(url)
  })
}

export function exportF5PoolMembers(id, params) {
  return api.get(`/f5/${id}/pool-members/export`, { params, responseType: 'blob' }).then((r) => {
    const url = URL.createObjectURL(r.data)
    const a = document.createElement('a')
    a.href = url
    a.download = `f5_pool_${id}.xlsx`
    a.click()
    URL.revokeObjectURL(url)
  })
}

export function exportF5Rules(id, params) {
  return api.get(`/f5/${id}/rules/export`, { params, responseType: 'blob' }).then((r) => {
    const url = URL.createObjectURL(r.data)
    const a = document.createElement('a')
    a.href = url
    a.download = `f5_rules_${id}.xlsx`
    a.click()
    URL.revokeObjectURL(url)
  })
}

export function exportF5ApplicationMap(id, params) {
  return api.get(`/f5/${id}/application-map/export`, { params, responseType: 'blob' }).then((r) => {
    const url = URL.createObjectURL(r.data)
    const a = document.createElement('a')
    a.href = url
    a.download = `f5_appmap_${id}.xlsx`
    a.click()
    URL.revokeObjectURL(url)
  })
}
