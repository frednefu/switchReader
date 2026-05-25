import api from './index'

export function getQAXDevices(params) {
  return api.get('/qax', { params }).then((r) => r.data)
}

export function getQAXDevice(id) {
  return api.get(`/qax/${id}`).then((r) => r.data)
}

export function createQAXDevice(data) {
  return api.post('/qax', data).then((r) => r.data)
}

export function updateQAXDevice(id, data) {
  return api.put(`/qax/${id}`, data).then((r) => r.data)
}

export function deleteQAXDevice(id) {
  return api.delete(`/qax/${id}`).then((r) => r.data)
}

export function triggerQAXScan(id) {
  return api.post(`/qax/${id}/scan`).then((r) => r.data)
}

export function testQAXConnection(data) {
  return api.post('/qax/test', data).then((r) => r.data)
}

export function scanAllQAXDevices() {
  return api.post('/qax/scan-all').then((r) => r.data)
}

export function deleteAllQAXDevices() {
  return api.delete('/qax/all').then((r) => r.data)
}

export function getQAXServers(id, params) {
  return api.get(`/qax/${id}/servers`, { params }).then((r) => r.data)
}

export function getQAXPorts(deviceId, serverId, params) {
  return api.get(`/qax/${deviceId}/servers/${serverId}/ports`, { params }).then((r) => r.data)
}

export function getQAXProcesses(deviceId, serverId, params) {
  return api.get(`/qax/${deviceId}/servers/${serverId}/processes`, { params }).then((r) => r.data)
}

export function getQAXSoftware(deviceId, serverId, params) {
  return api.get(`/qax/${deviceId}/servers/${serverId}/software`, { params }).then((r) => r.data)
}
