import { useState, useEffect } from 'react'
import axios from 'axios'
import { buildApiUrl } from '../config/api'

export function useGraph() {
  const [graphData, setGraphData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    const fetchGraph = async () => {
      try {
        const response = await axios.get(buildApiUrl('/api/graph/'))
        setGraphData(response.data)
        setError(null)
      } catch (err) {
        const errorMsg = err.response?.data?.detail || (err.response ? err.message : 'Network error: cannot reach backend API. Check VITE_API_BASE_URL and backend status.')
        setError(errorMsg)
        console.error('Error fetching graph:', err)
      } finally {
        setLoading(false)
      }
    }

    fetchGraph()
  }, [])

  return { graphData, loading, error }
}
