import { useState } from 'react'
import axios from 'axios'
import { buildApiUrl } from '../config/api'

export function useChat() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const sendMessage = async (message, history = [], apiKey = '') => {
    setLoading(true)
    setError(null)

    try {
      const response = await axios.post(buildApiUrl('/api/chat/'), {
        message,
        conversation_history: history,
        api_key: apiKey || undefined
      })
      return response.data
    } catch (err) {
      const errorMsg = err.response?.data?.detail || err.message
      setError(errorMsg)
      console.error('Error sending message:', err)
      return null
    } finally {
      setLoading(false)
    }
  }

  const validateApiKey = async (apiKey = '') => {
    const key = String(apiKey || '').trim()
    if (!key) {
      return { valid: false, message: 'Please enter an API key first.' }
    }

    try {
      const response = await axios.post(buildApiUrl('/api/chat/validate-key'), {
        api_key: key
      })
      return {
        valid: true,
        message: response.data?.message || 'API key is valid.',
        model: response.data?.model || ''
      }
    } catch (err) {
      const detail = err.response?.data?.detail || err.message
      return { valid: false, message: detail }
    }
  }

  return { sendMessage, validateApiKey, loading, error }
}
