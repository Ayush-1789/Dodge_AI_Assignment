import React, { useState } from 'react'
import Header from './components/Header'
import GraphCanvas from './components/GraphCanvas'
import ChatPanel from './components/ChatPanel'
import NodeInspector from './components/NodeInspector'
import './App.css'

export default function App() {
  const [selectedNode, setSelectedNode] = useState(null)
  const [highlightedNodes, setHighlightedNodes] = useState([])
  const [focusedResponseNodes, setFocusedResponseNodes] = useState([])
  const [nodeMetadata, setNodeMetadata] = useState(null)

  const handleNodeClick = (nodeId) => {
    setSelectedNode(nodeId)
  }

  const handleCloseInspector = () => {
    setSelectedNode(null)
    setNodeMetadata(null)
  }

  return (
    <div className="app-wrapper">
      <Header />
      
      <main className="app-main">
        {/* Graph Canvas - Left Panel */}
        <div className="graph-container">
          <GraphCanvas
            onNodeClick={handleNodeClick}
            highlightedNodes={highlightedNodes}
            focusedNodes={focusedResponseNodes}
          />
        </div>

        {/* Chat Panel - Right Panel */}
        <div className="chat-container">
          <ChatPanel
            onHighlightNodes={setHighlightedNodes}
            onFocusNodes={setFocusedResponseNodes}
            onSelectNode={handleNodeClick}
            selectedNode={selectedNode}
          />
        </div>

        {/* Node Inspector - Overlay Modal */}
        {selectedNode && (
          <NodeInspector
            nodeId={selectedNode}
            onClose={handleCloseInspector}
          />
        )}
      </main>
    </div>
  )
}
