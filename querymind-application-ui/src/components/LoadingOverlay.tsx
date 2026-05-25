import { useStore } from '../store/usestore'

export function LoadingOverlay() {
  const { loading, loadingText } = useStore()
  if (!loading) return null
  return (
    <div className="loading-overlay">
      <div className="loading-spinner">
        <div className="spinner" />
        <span className="spinner-text">{loadingText || 'Loading...'}</span>
      </div>
    </div>
  )
}