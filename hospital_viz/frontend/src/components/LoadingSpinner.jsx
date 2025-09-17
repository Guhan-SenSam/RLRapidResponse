import './LoadingSpinner.css'

const LoadingSpinner = () => {
  return (
    <div className="loading-overlay">
      <div className="loading-spinner">
        <div className="spinner"></div>
        <p className="loading-text">Loading hospital data...</p>
      </div>
    </div>
  )
}

export default LoadingSpinner