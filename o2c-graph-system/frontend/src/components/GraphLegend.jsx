import React from 'react'
import './GraphLegend.css'

export default function GraphLegend() {
  const nodeTypes = [
    { type: 'Sales Order', color: '#4A90D9' },
    { type: 'Sales Order Item', color: '#5BA85A' },
    { type: 'Customer', color: '#E8A838' },
    { type: 'Material', color: '#9B59B6' },
    { type: 'Delivery', color: '#E74C3C' },
    { type: 'Billing Document', color: '#1ABC9C' },
    { type: 'Journal Entry', color: '#F39C12' },
    { type: 'Address', color: '#95A5A6' },
    { type: 'Collapsed Hub', color: '#22d3ee' }
  ]

  return (
    <div className="graph-legend">
      <div className="legend-title">NODE TYPES</div>
      <div className="legend-items">
        {nodeTypes.map((item) => (
          <div key={item.type} className="legend-item">
            <div className="legend-color" style={{ backgroundColor: item.color }}></div>
            <span className="legend-label">{item.type}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
