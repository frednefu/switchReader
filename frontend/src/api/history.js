import api from './index'

export function getHistory(params) {
  return api.get('/history', { params }).then((r) => r.data)
}

export function getHistoryByIp(ip) {
  return api.get(`/history/ip/${encodeURIComponent(ip)}`).then((r) => r.data)
}

export function getHistoryByMac(mac) {
  return api.get(`/history/mac/${encodeURIComponent(mac)}`).then((r) => r.data)
}
