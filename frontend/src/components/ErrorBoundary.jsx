import React from 'react'
import { AlertTriangle, RotateCcw, Home } from 'lucide-react'

export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, errorInfo) {
    console.error('[PLUTO ErrorBoundary caught an error]:', error, errorInfo)
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null })
    if (this.props.onReset) {
      this.props.onReset()
    } else {
      window.location.reload()
    }
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-[400px] flex items-center justify-center p-6">
          <div className="max-w-lg w-full bg-white border-[3px] border-black rounded-2xl p-8 shadow-[6px_6px_0px_0px_#000] text-center space-y-5">
            <div className="w-16 h-16 bg-[#FF4D4D] border-[3px] border-black rounded-2xl text-black mx-auto flex items-center justify-center shadow-[4px_4px_0px_0px_#000] rotate-[-4deg]">
              <AlertTriangle className="w-8 h-8 stroke-[2.5]" />
            </div>
            <div>
              <h2 className="text-2xl font-black text-black uppercase tracking-tight">Something Went Wrong</h2>
              <p className="text-xs font-bold text-slate-600 mt-2">
                An unexpected interface error occurred. Your session data is safely preserved.
              </p>
              {this.state.error?.message && (
                <div className="mt-3 p-3 bg-[#F4F0EA] border border-black rounded-lg text-left font-mono text-[11px] text-red-700 overflow-x-auto">
                  {this.state.error.message}
                </div>
              )}
            </div>
            <div className="flex items-center justify-center gap-3 pt-2">
              <button
                onClick={this.handleReset}
                className="px-5 py-2.5 rounded-xl bg-[#FFE600] hover:bg-[#ffdf00] border-2 border-black font-black text-black text-xs uppercase shadow-[3px_3px_0px_0px_#000] flex items-center space-x-1.5"
              >
                <RotateCcw className="w-4 h-4 stroke-[2.5]" />
                <span>Try Again</span>
              </button>
              <button
                onClick={() => {
                  sessionStorage.clear()
                  window.location.href = '/'
                }}
                className="px-5 py-2.5 rounded-xl bg-white hover:bg-slate-100 border-2 border-black font-black text-black text-xs uppercase shadow-[3px_3px_0px_0px_#000] flex items-center space-x-1.5"
              >
                <Home className="w-4 h-4 stroke-[2.5]" />
                <span>Return to Home</span>
              </button>
            </div>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}

