import api from './index'

export function getAssetProfile(params) {
  return api.get('/asset-profile', { params }).then((r) => r.data)
}
