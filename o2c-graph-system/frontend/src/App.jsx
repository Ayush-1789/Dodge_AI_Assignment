import React, { useState } from 'react'
import Header from './components/Header'
import GraphCanvas from './components/GraphCanvas'
import ChatPanel from './components/ChatPanel'
import './App.css'

export default function App() {
  const [highlightedNodes, setHighlightedNodes] = useState([])
  const [focusedResponseNodes, setFocusedResponseNodes] = useState([])

  return (
    <div className="app-wrapper">
      <Header />
      
      <main className="app-main">
        {/* Graph Canvas - Left Panel */}
        <div className="graph-container">
          <GraphCanvas
            highlightedNodes={highlightedNodes}
            focusedNodes={focusedResponseNodes}
          />
        </div>

        {/* Chat Panel - Right Panel */}
        <div className="chat-container">
          <ChatPanel
            onHighlightNodes={setHighlightedNodes}
            onFocusNodes={setFocusedResponseNodes}
          />
        </div>
      </main>
    </div>
  )
}
