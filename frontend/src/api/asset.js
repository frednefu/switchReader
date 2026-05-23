import api from './index'

export function getAssetProfile(params) {
  return api.get('/asset-profile', { params }).then((r) => r.data)
}

export function exportAssetProfile(params) {
  return api.get('/asset-profile/export', { params, responseType: 'blob' }).then((r) => {
    const url = URL.createObjectURL(r.data)
    const a = document.createElement('a')
    a.href = url
    a.download = 'asset_profile.xlsx'
    a.click()
    URL.revokeObjectURL(url)
  })
}
