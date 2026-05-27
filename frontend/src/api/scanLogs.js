import api from './index'

export function getScanLogs(params) {
  return api.get('/scan-logs', { params }).then((r) => r.data)
}

export function getScanLog(id) {
  return api.get(`/scan-logs/${id}`).then((r) => r.data)
}

export function getScanSteps(logId) {
  return api.get(`/scan-logs/${logId}/steps`).then((r) => r.data)
}

export function getScanOutput(logId) {
  return api.get(`/scan-logs/${logId}/output`).then((r) => r.data)
}

export function deleteScanLog(id) {
  return api.delete(`/scan-logs/${id}`).then((r) => r.data)
}

export function clearScanLogs(sourceType, status) {
  const params = {}
  if (sourceType) params.source_type = sourceType
  if (status) params.status = status
  return api.delete('/scan-logs', { params }).then((r) => r.data)
}
