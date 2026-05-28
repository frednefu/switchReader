import api from './index'

export function getConfig() {
  return api.get('/sys/api-config').then((r) => r.data)
}

export function saveConfig(data) {
  return api.put('/sys/api-config', data).then((r) => r.data)
}

export function testConfig() {
  return api.post('/sys/api-config/test').then((r) => r.data)
}
