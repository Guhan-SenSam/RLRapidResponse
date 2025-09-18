import { useState, useEffect } from 'react'

const HospitalFilters = ({ hospitals, onFiltersChange }) => {
  const [filters, setFilters] = useState({
    type: '',
    status: '',
    state: '',
    bedRange: '',
    showFilters: false
  })

  const [filterOptions, setFilterOptions] = useState({
    types: [],
    statuses: [],
    states: [],
    bedRanges: [
      { value: '', label: 'All bed counts' },
      { value: 'small', label: 'Small (1-50 beds)' },
      { value: 'medium', label: 'Medium (51-200 beds)' },
      { value: 'large', label: 'Large (201-500 beds)' },
      { value: 'very-large', label: 'Very Large (500+ beds)' },
      { value: 'unknown', label: 'Unknown bed count' }
    ]
  })

  // Extract unique values from hospital data
  useEffect(() => {
    if (!hospitals.length) return

    const types = new Set([''])
    const statuses = new Set([''])
    const states = new Set([''])

    hospitals.forEach(hospital => {
      if (hospital.type && hospital.type !== 'Not specified') {
        types.add(hospital.type)
      }
      if (hospital.status && hospital.status !== 'Unknown') {
        statuses.add(hospital.status)
      }
      if (hospital.state) {
        states.add(hospital.state)
      }
    })

    setFilterOptions(prev => ({
      ...prev,
      types: [
        { value: '', label: 'All types' },
        ...Array.from(types).filter(t => t).sort().map(type => ({
          value: type,
          label: type
        }))
      ],
      statuses: [
        { value: '', label: 'All statuses' },
        ...Array.from(statuses).filter(s => s).sort().map(status => ({
          value: status,
          label: status
        }))
      ],
      states: [
        { value: '', label: 'All states' },
        ...Array.from(states).filter(s => s).sort().map(state => ({
          value: state,
          label: state
        }))
      ]
    }))
  }, [hospitals])

  // Apply filters whenever they change
  useEffect(() => {
    const filteredHospitals = hospitals.filter(hospital => {
      // Type filter
      if (filters.type && hospital.type !== filters.type) {
        return false
      }

      // Status filter
      if (filters.status && hospital.status !== filters.status) {
        return false
      }

      // State filter
      if (filters.state && hospital.state !== filters.state) {
        return false
      }

      // Bed range filter
      if (filters.bedRange) {
        const beds = hospital.beds || 0
        switch (filters.bedRange) {
          case 'small':
            if (beds <= 0 || beds > 50) return false
            break
          case 'medium':
            if (beds <= 50 || beds > 200) return false
            break
          case 'large':
            if (beds <= 200 || beds > 500) return false
            break
          case 'very-large':
            if (beds <= 500) return false
            break
          case 'unknown':
            if (beds > 0 && beds !== -999) return false
            break
        }
      }

      return true
    })

    onFiltersChange(filteredHospitals, filters)
  }, [filters, hospitals, onFiltersChange])

  const handleFilterChange = (filterType, value) => {
    setFilters(prev => ({
      ...prev,
      [filterType]: value
    }))
  }

  const clearAllFilters = () => {
    setFilters(prev => ({
      ...prev,
      type: '',
      status: '',
      state: '',
      bedRange: ''
    }))
  }

  const hasActiveFilters = filters.type || filters.status || filters.state || filters.bedRange

  const toggleFilters = () => {
    setFilters(prev => ({
      ...prev,
      showFilters: !prev.showFilters
    }))
  }

  return (
    <div className="hospital-filters">
      <button
        className="toggle-filters-button"
        onClick={toggleFilters}
        type="button"
      >
        🔽 Filters {hasActiveFilters && <span className="active-filters-indicator">●</span>}
      </button>

      {filters.showFilters && (
        <div className="filters-panel">
          <div className="filters-grid">
            <div className="filter-group">
              <label htmlFor="type-filter">Hospital Type</label>
              <select
                id="type-filter"
                value={filters.type}
                onChange={(e) => handleFilterChange('type', e.target.value)}
                className="filter-select"
              >
                {filterOptions.types.map(option => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="filter-group">
              <label htmlFor="status-filter">Status</label>
              <select
                id="status-filter"
                value={filters.status}
                onChange={(e) => handleFilterChange('status', e.target.value)}
                className="filter-select"
              >
                {filterOptions.statuses.map(option => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="filter-group">
              <label htmlFor="state-filter">State</label>
              <select
                id="state-filter"
                value={filters.state}
                onChange={(e) => handleFilterChange('state', e.target.value)}
                className="filter-select"
              >
                {filterOptions.states.map(option => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="filter-group">
              <label htmlFor="bed-range-filter">Bed Count</label>
              <select
                id="bed-range-filter"
                value={filters.bedRange}
                onChange={(e) => handleFilterChange('bedRange', e.target.value)}
                className="filter-select"
              >
                {filterOptions.bedRanges.map(option => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {hasActiveFilters && (
            <div className="filter-actions">
              <button
                onClick={clearAllFilters}
                className="clear-filters-button"
                type="button"
              >
                Clear All Filters
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default HospitalFilters