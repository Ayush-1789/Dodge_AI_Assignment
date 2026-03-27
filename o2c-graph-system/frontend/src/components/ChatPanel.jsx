import React, { useState, useRef, useEffect } from 'react'
import { useChat } from '../hooks/useChat'
import MessageBubble from './MessageBubble'
import './ChatPanel.css'

const EXAMPLE_QUERIES = [
  'Which customers have the most orders?',
  'Show billing documents from last month',
  'Find incomplete deliveries',
  'List high-value orders'
]

const INITIAL_ASSISTANT_MESSAGE = {
  role: 'assistant',
  content: 'Hello! How can I help you with your Order-to-Cash data today?',
  highlighted_nodes: [],
  query_type: 'greeting'
}

export default function ChatPanel({ onHighlightNodes, onFocusNodes }) {
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState([INITIAL_ASSISTANT_MESSAGE])
  const messagesEndRef = useRef(null)
  const { sendMessage, loading, error } = useChat()

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!input.trim() || loading) return

    const userInput = input.trim()
    setInput('')

    // Add user message
    const userMsg = { role: 'user', content: userInput }
    setMessages(prev => [...prev, userMsg])

    // Get response
    const response = await sendMessage(userInput, messages)
    if (response) {
      const responseNodes = response.highlighted_nodes || []
      const assistantMsg = {
        role: 'assistant',
        content: response.answer,
        highlighted_nodes: responseNodes,
        query_type: response.query_type || 'unknown'
      }
      setMessages(prev => [...prev, assistantMsg])
      onHighlightNodes?.(responseNodes)
      onFocusNodes?.(responseNodes)
    }
  }

  const handleExampleQuery = (query) => {
    setInput(query)
  }

  return (
    <div className="chat-panel">
      {/* Header */}
      <div className="chat-header">
        <h2 className="chat-title">Query Assistant</h2>
        <p className="chat-subtitle">Ask questions about your Order-to-Cash data</p>
      </div>

      {/* Messages Area */}
      <div className="chat-messages">
        <div className="messages-list">
          {messages.map((msg, idx) => (
            <MessageBubble key={idx} message={msg} />
          ))}

          {messages.length <= 1 && (
            <div className="example-queries" style={{ marginTop: '8px' }}>
              {EXAMPLE_QUERIES.map((query, idx) => (
                <button
                  key={idx}
                  className="example-button"
                  onClick={() => handleExampleQuery(query)}
                >
                  <span className="example-icon">→</span>
                  <span>{query}</span>
                </button>
              ))}
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Error Display */}
      {error && (
        <div className="chat-error">
          <span className="error-icon">⚠️</span>
          <span>{error}</span>
        </div>
      )}

      {/* Input Area */}
      <div className="chat-input-area">
        <form onSubmit={handleSubmit}>
          <div className="input-wrapper">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about orders, deliveries, billing..."
              disabled={loading}
              className="chat-input"
              autoFocus
            />
            <button
              type="submit"
              disabled={loading || !input.trim()}
              className="send-button"
              title={loading ? 'Processing...' : 'Send message'}
            >
              {loading ? (
                <span className="spinner-small"></span>
              ) : (
                <span className="send-icon">↗</span>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

