import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '../services/api'

export interface UsageSummary {
  total_tokens: number
  prompt_tokens: number
  completion_tokens: number
  chat_tokens: number
  classroom_tokens: number
  other_tokens: number
  requests: number
}

export interface UsageSource {
  source: string
  label: string
  tokens: number
  requests: number
}

export interface UsageKind {
  kind: string
  label: string
  tokens: number
  quantity: number
  unit: string
  requests: number
}

export interface UsageModel {
  model_name: string
  provider: string
  kind: string
  requests: number
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
  quantity: number
  unit: string
}

export interface UsageDaily {
  date: string
  total_tokens: number
  chat_tokens: number
  classroom_tokens: number
  other_tokens: number
  requests: number
  chat_requests?: number
  classroom_requests?: number
  other_requests?: number
}

export interface UsageRecord {
  id: string
  created_at: string
  source: string
  source_label: string
  kind: string
  provider: string
  model_name: string
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
  quantity: number
  unit: string
}

export interface UsageDashboardData {
  totals: UsageSummary
  summary: UsageSummary
  by_source: UsageSource[]
  by_kind: UsageKind[]
  by_model: UsageModel[]
  by_day: UsageDaily[]
  daily: UsageDaily[]
  recent_records: UsageRecord[]
  days?: number | null
  source_filter?: string | null
}

export const useUsageStore = defineStore('usage', () => {
  const dashboard = ref<UsageDashboardData | null>(null)
  const loading = ref(false)
  const syncing = ref(false)
  const days = ref(30)
  const sourceFilter = ref('all')

  const totals = computed<UsageSummary>(() => {
    return dashboard.value?.totals || {
      total_tokens: 0,
      prompt_tokens: 0,
      completion_tokens: 0,
      chat_tokens: 0,
      classroom_tokens: 0,
      other_tokens: 0,
      requests: 0,
    }
  })

  const dailyTrend = computed<UsageDaily[]>(() => {
    return dashboard.value?.by_day || dashboard.value?.daily || []
  })

  const bySource = computed<UsageSource[]>(() => {
    return dashboard.value?.by_source || []
  })

  const byKind = computed<UsageKind[]>(() => {
    return dashboard.value?.by_kind || []
  })

  const byModel = computed<UsageModel[]>(() => {
    return dashboard.value?.by_model || []
  })

  const recentRecords = computed<UsageRecord[]>(() => {
    return dashboard.value?.recent_records || []
  })

  async function fetchDashboard(customDays?: number, customSource?: string) {
    if (customDays !== undefined) days.value = customDays
    if (customSource !== undefined) sourceFilter.value = customSource

    loading.value = true
    try {
      const params = new URLSearchParams()
      params.append('days', String(days.value))
      if (sourceFilter.value && sourceFilter.value !== 'all') {
        params.append('source', sourceFilter.value)
      }
      const resp = await api.get(`/usage/dashboard?${params.toString()}`)
      dashboard.value = resp.data
      return resp.data
    } catch (err) {
      console.error('Failed to fetch usage dashboard:', err)
      throw err
    } finally {
      loading.value = false
    }
  }

  async function syncClassroom() {
    syncing.value = true
    try {
      const resp = await api.post('/usage/sync')
      await fetchDashboard()
      return resp.data
    } catch (err) {
      console.error('Failed to sync classroom usage:', err)
      throw err
    } finally {
      syncing.value = false
    }
  }

  return {
    dashboard,
    loading,
    syncing,
    days,
    sourceFilter,
    totals,
    dailyTrend,
    bySource,
    byKind,
    byModel,
    recentRecords,
    fetchDashboard,
    syncClassroom,
  }
})
