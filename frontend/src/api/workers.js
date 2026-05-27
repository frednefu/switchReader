import api from './index'

export function getWorkers(params) {
  return api.get('/workers', { params }).then((r) => r.data)
}

export function getWorker(id) {
  return api.get(`/workers/${id}`).then((r) => r.data)
}

export function registerWorker(data) {
  return api.post('/workers/register', data).then((r) => r.data)
}

export function deleteWorker(id) {
  return api.delete(`/workers/${id}`).then((r) => r.data)
}
