import { useState } from 'react'

const SearchBox = ({ onLocationFound }) => {
  const [searchTerm, setSearchTerm] = useState('')
  const [isSearching, setIsSearching] = useState(false)
  const [error, setError] = useState('')

  const handleSearch = async (e) => {
    e.preventDefault()
    if (!searchTerm.trim()) return

    setIsSearching(true)
    setError('')

    try {
      // Using Nominatim (OpenStreetMap) geocoding service
      const response = await fetch(
        `https://nominatim.openstreetmap.org/search?format=json&limit=1&countrycodes=us&q=${encodeURIComponent(searchTerm.trim())}`
      )

      const data = await response.json()

      if (data && data.length > 0) {
        const result = data[0]
        const lat = parseFloat(result.lat)
        const lon = parseFloat(result.lon)

        onLocationFound({
          lat,
          lon,
          name: result.display_name,
          zoom: 10
        })
        setError('')
      } else {
        setError('Location not found. Try searching for a US city or state.')
      }
    } catch (err) {
      setError('Search failed. Please try again.')
      console.error('Search error:', err)
    } finally {
      setIsSearching(false)
    }
  }

  const handleClear = () => {
    setSearchTerm('')
    setError('')
  }

  return (
    <div className="search-box">
      <form onSubmit={handleSearch} className="search-form">
        <div className="search-input-container">
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search for a city or state..."
            className="search-input"
            disabled={isSearching}
          />
          {searchTerm && (
            <button
              type="button"
              onClick={handleClear}
              className="clear-button"
              disabled={isSearching}
            >
              ×
            </button>
          )}
        </div>
        <button
          type="submit"
          className="search-button"
          disabled={isSearching || !searchTerm.trim()}
        >
          {isSearching ? '🔍' : '🔍'}
        </button>
      </form>
      {error && <div className="search-error">{error}</div>}
    </div>
  )
}

export default SearchBox