import { type AxiosResponse, type AxiosError } from 'axios'
import { useToastStore } from '../stores/toast'

interface UseApiOptions {
  showError?: boolean
  errorMessage?: string
}

/**
 * Composable for unified API request handling with error management
 */
export function useApi() {
  const toast = useToastStore()

  /**
   * Execute an API call with automatic error handling
   * @param apiCall - The API call function
   * @param options - Configuration options
   * @returns The response data or null on error
   */
  async function request<T>(
    apiCall: () => Promise<AxiosResponse<T>>,
    options: UseApiOptions = {}
  ): Promise<T | null> {
    const { showError = true, errorMessage } = options

    try {
      const response = await apiCall()
      return response.data
    } catch (error) {
      const axiosError = error as AxiosError<{ detail: string }>

      if (showError) {
        const message =
          errorMessage ||
          axiosError.response?.data?.detail ||
          axiosError.message ||
          '请求失败'
        toast.error(message)
      }

      return null
    }
  }

  /**
   * Execute an API call and throw on error
   * @param apiCall - The API call function
   * @returns The response data
   * @throws The error if the call fails
   */
  async function requestOrThrow<T>(
    apiCall: () => Promise<AxiosResponse<T>>
  ): Promise<T> {
    const response = await apiCall()
    return response.data
  }

  return {
    request,
    requestOrThrow
  }
}
