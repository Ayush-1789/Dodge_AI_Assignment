import React from 'react'
import './Header.css'

export default function Header() {
  return (
    <header className="header">
      <div className="header-content">
        <div className="header-left">
          <div className="logo">
            <div className="logo-mark">◆</div>
            <div className="logo-text">
              <h1 className="logo-title">O2C Graph</h1>
              <p className="logo-subtitle">Order-to-Cash Intelligence</p>
            </div>
          </div>
        </div>

        <div className="header-center">
          <nav className="breadcrumb">
            <span>Mapping</span>
            <span className="separator">/</span>
            <span className="active">Order-to-Cash Graph</span>
          </nav>
        </div>

        <div className="header-right">
          <div className="status-badge">
            <div className="status-dot"></div>
            <span>Backend Connected</span>
          </div>
        </div>
      </div>
    </header>
  )
}
