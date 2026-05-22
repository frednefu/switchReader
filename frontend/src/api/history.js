import api from './index'

export function getHistory(params) {
  return api.get('/history', { params }).then((r) => r.data)
}

export function getHistoryByIp(ip, extra = {}) {
  return api.get(`/history/ip/${encodeURIComponent(ip)}`, { params: extra }).then((r) => r.data)
}

export function getHistoryByMac(mac, extra = {}) {
  return api.get(`/history/mac/${encodeURIComponent(mac)}`, { params: extra }).then((r) => r.data)
}
