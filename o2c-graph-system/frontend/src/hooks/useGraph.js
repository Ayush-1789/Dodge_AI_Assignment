import { useState, useEffect } from 'react'
import axios from 'axios'

export function useGraph() {
  const [graphData, setGraphData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    const fetchGraph = async () => {
      try {
        const response = await axios.get('/api/graph/')
        setGraphData(response.data)
        setError(null)
      } catch (err) {
        setError(err.message)
        console.error('Error fetching graph:', err)
      } finally {
        setLoading(false)
      }
    }

    fetchGraph()
  }, [])

  return { graphData, loading, error }
}
