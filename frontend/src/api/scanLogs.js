import api from './index'

export function getScanLogs(params) {
  return api.get('/scan-logs', { params }).then((r) => r.data)
}

export function getScanLog(id) {
  return api.get(`/scan-logs/${id}`).then((r) => r.data)
}

export function clearScanLogs(sourceType) {
  const params = {}
  if (sourceType) params.source_type = sourceType
  return api.delete('/scan-logs', { params }).then((r) => r.data)
}
