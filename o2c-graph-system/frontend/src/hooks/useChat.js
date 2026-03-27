import { useState } from 'react'
import axios from 'axios'
import { buildApiUrl } from '../config/api'

export function useChat() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const sendMessage = async (message, history = []) => {
    setLoading(true)
    setError(null)

    try {
      const response = await axios.post(buildApiUrl('/api/chat/'), {
        message,
        conversation_history: history
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

  return { sendMessage, loading, error }
}
