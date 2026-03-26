import React, { useState, useEffect } from 'react'
import axios from 'axios'
import './NodeInspector.css'

export default function NodeInspector({ nodeId, onClose }) {
  const [nodeData, setNodeData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    const fetchNodeData = async () => {
      try {
        setLoading(true)
        const response = await axios.get(`/api/graph/node/${nodeId}`)
        setNodeData(response.data)
        setError(null)
      } catch (err) {
        console.error('Error fetching node:', err)
        setError('Failed to load node details')
      } finally {
        setLoading(false)
      }
    }
    fetchNodeData()
  }, [nodeId])

  // Close on Escape key
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        onClose()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [onClose])

  return (
    <>
      {/* Backdrop */}
      <div className="inspector-backdrop" onClick={onClose}></div>

      {/* Inspector Panel */}
      <div className="node-inspector">
        {/* Header */}
        <div className="inspector-header">
          <div className="inspector-title">
            <h3>{nodeData?.type || 'Node'}</h3>
            <p>{nodeId}</p>
          </div>
          <button className="inspector-close" onClick={onClose} title="Close (Esc)">
            ✕
          </button>
        </div>

        {/* Content */}
        <div className="inspector-content">
          {loading ? (
            <div className="inspector-loading">
              <div className="spinner"></div>
              <p>Loading node details...</p>
            </div>
          ) : error ? (
            <div className="inspector-error">
              <p>⚠️ {error}</p>
            </div>
          ) : nodeData ? (
            <>
              {/* Properties */}
              <section className="inspector-section">
                <h4 className="section-title">Properties</h4>
                <div className="properties-table">
                  {Object.entries(nodeData.properties || {}).map(([key, value]) => (
                    <div key={key} className="property-row">
                      <span className="property-key">{key}</span>
                      <span className="property-value">{String(value)}</span>
                    </div>
                  ))}
                </div>
              </section>

              {/* Metrics */}
              <section className="inspector-section">
                <h4 className="section-title">Graph Metrics</h4>
                <div className="metrics-grid">
                  <div className="metric-card">
                    <div className="metric-label">Incoming Edges</div>
                    <div className="metric-value">{nodeData.in_degree || 0}</div>
                  </div>
                  <div className="metric-card">
                    <div className="metric-label">Outgoing Edges</div>
                    <div className="metric-value">{nodeData.out_degree || 0}</div>
                  </div>
                  <div className="metric-card">
                    <div className="metric-label">Total Degree</div>
                    <div className="metric-value">
                      {(nodeData.in_degree || 0) + (nodeData.out_degree || 0)}
                    </div>
                  </div>
                </div>
              </section>
            </>
          ) : null}
        </div>
      </div>
    </>
  )
}

