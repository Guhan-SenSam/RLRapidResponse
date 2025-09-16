import { useState, useEffect, useRef } from 'react'
import HospitalMap from './components/HospitalMap'
import LoadingSpinner from './components/LoadingSpinner'
import SearchBox from './components/SearchBox'
import HospitalFilters from './components/HospitalFilters'
import axios from 'axios'
import './App.css'

const API_BASE_URL = 'http://localhost:9000/api'

function App() {
  const [hospitals, setHospitals] = useState([])
  const [filteredHospitals, setFilteredHospitals] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [hospitalCount, setHospitalCount] = useState(0)
  const [activeFilters, setActiveFilters] = useState({})
  const mapRef = useRef()

  useEffect(() => {
    loadHospitalData()
  }, [])

  const loadHospitalData = async () => {
    try {
      setLoading(true)
      setError(null)

      // First get the count to show progress
      const countResponse = await axios.get(`${API_BASE_URL}/hospitals/count`)
      setHospitalCount(countResponse.data.count)

      // Then load the actual data
      const response = await axios.get(`${API_BASE_URL}/hospitals`)
      setHospitals(response.data.hospitals)
      setFilteredHospitals(response.data.hospitals)
    } catch (err) {
      setError('Failed to load hospital data: ' + err.message)
      console.error('Error loading hospitals:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleLocationFound = (location) => {
    mapRef.current?.flyTo(location.lat, location.lon, location.zoom)
  }

  const handleFiltersChange = (filtered, filters) => {
    setFilteredHospitals(filtered)
    setActiveFilters(filters)
  }

  const hasActiveFilters = activeFilters.type || activeFilters.status || activeFilters.state || activeFilters.bedRange

  return (
    <div className="app">
      <header className="app-header">
        <h1>US Hospital Locations</h1>
        <SearchBox onLocationFound={handleLocationFound} />
        <HospitalFilters hospitals={hospitals} onFiltersChange={handleFiltersChange} />
        <div className="stats">
          {hospitalCount > 0 && (
            <span className="hospital-count">
              {loading ? `Loading ${hospitalCount} hospitals...` :
                hasActiveFilters ?
                  `${filteredHospitals.length} of ${hospitals.length} hospitals displayed (filtered)` :
                  `${hospitals.length} hospitals displayed (clustered)`
              }
            </span>
          )}
        </div>
      </header>

      <main className="app-main">
        {error && (
          <div className="error-message">
            {error}
            <button onClick={loadHospitalData} className="retry-button">
              Retry
            </button>
          </div>
        )}

        <div className="map-container">
          <HospitalMap ref={mapRef} hospitals={filteredHospitals} loading={loading} />
          {loading && <LoadingSpinner />}
        </div>
      </main>
    </div>
  )
}

export default App
