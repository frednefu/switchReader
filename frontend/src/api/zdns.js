import api from './index'

export function getZDNSDevices(params) {
  return api.get('/zdns', { params }).then((r) => r.data)
}

export function getZDNSDevice(id) {
  return api.get(`/zdns/${id}`).then((r) => r.data)
}

export function createZDNSDevice(data) {
  return api.post('/zdns', data).then((r) => r.data)
}

export function updateZDNSDevice(id, data) {
  return api.put(`/zdns/${id}`, data).then((r) => r.data)
}

export function deleteZDNSDevice(id) {
  return api.delete(`/zdns/${id}`).then((r) => r.data)
}

export function triggerZDNSScan(id) {
  return api.post(`/zdns/${id}/scan`).then((r) => r.data)
}

export function testZDNSConnection(data) {
  return api.post('/zdns/test', data).then((r) => r.data)
}

export function triggerZDNSIPScan(id) {
  return api.post(`/zdns/${id}/ip-scan`).then((r) => r.data)
}

export function scanAllZDNSDevices() {
  return api.post('/zdns/scan-all').then((r) => r.data)
}

export function deleteAllZDNSDevices() {
  return api.delete('/zdns/all').then((r) => r.data)
}

export function getZDNSRecords(id, params) {
  return api.get(`/zdns/${id}/records`, { params }).then((r) => r.data)
}

export function getZDNSDomainMap(id, params) {
  return api.get(`/zdns/${id}/domain-map`, { params }).then((r) => r.data)
}

export function exportZDNSRecords(id, params) {
  return api.get(`/zdns/${id}/records/export`, { params, responseType: 'blob' }).then((r) => {
    const url = URL.createObjectURL(r.data)
    const a = document.createElement('a')
    a.href = url
    a.download = `zdns_records_${id}.xlsx`
    a.click()
    URL.revokeObjectURL(url)
  })
}

export function exportZDNSDomainMap(id, params) {
  return api.get(`/zdns/${id}/domain-map/export`, { params, responseType: 'blob' }).then((r) => {
    const url = URL.createObjectURL(r.data)
    const a = document.createElement('a')
    a.href = url
    a.download = `zdns_domainmap_${id}.xlsx`
    a.click()
    URL.revokeObjectURL(url)
  })
}
