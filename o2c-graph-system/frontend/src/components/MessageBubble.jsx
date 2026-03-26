import React from 'react'
import './MessageBubble.css'

export default function MessageBubble({ message }) {
  const isUser = message.role === 'user'
  const highlightedNodes = message.highlighted_nodes || []

  return (
    <div className={`message-bubble ${isUser ? 'user-message' : 'assistant-message'}`}>
      <div className="message-content">
        <p>{message.content}</p>
      </div>

      {/* Query Type Badge */}
      {message.query_type && !isUser && (
        <div className="message-badge">
          {message.query_type.toUpperCase()}
        </div>
      )}

      {/* Highlighted Nodes */}
      {highlightedNodes.length > 0 && !isUser && (
        <div className="highlighted-nodes">
          {highlightedNodes.slice(0, 3).map(nodeId => {
            const [type, id] = nodeId.split('_')
            return (
              <span key={nodeId} className="node-tag" title={nodeId}>
                <span className="node-type">{type}</span>
                <span className="node-id">{id}</span>
              </span>
            )
          })}
          {highlightedNodes.length > 3 && (
            <span className="node-more">
              +{highlightedNodes.length - 3}
            </span>
          )}
        </div>
      )}
    </div>
  )
}

