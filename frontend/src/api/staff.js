import api from './index'

export function lookupStaff(gh, xm) {
  return api.post('/sys/staff/lookup', { gh, xm }).then((r) => r.data)
}
