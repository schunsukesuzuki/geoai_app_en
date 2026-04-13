import React from 'react'

export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="fatal-shell">
          <h1>A frontend exception occurred</h1>
          <p>Rendering has been stopped to prevent the whole screen from going blank.</p>
          <pre>{String(this.state.error?.message || this.state.error || 'Unknown error')}</pre>
        </div>
      )
    }
    return this.props.children
  }
}
