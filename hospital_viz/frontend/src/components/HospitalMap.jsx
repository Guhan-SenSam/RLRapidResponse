import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet'
import { useEffect, useRef, useImperativeHandle, forwardRef } from 'react'
import 'leaflet/dist/leaflet.css'
import 'leaflet.markercluster/dist/MarkerCluster.css'
import 'leaflet.markercluster/dist/MarkerCluster.Default.css'
import L from 'leaflet'
import 'leaflet.markercluster'

// Fix for default markers in React Leaflet
delete L.Icon.Default.prototype._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
})

// Custom hospital icon - red square
const hospitalIcon = new L.Icon({
  iconUrl: 'data:image/svg+xml;base64,' + btoa(`
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="#dc2626" width="16" height="16">
      <rect x="0" y="0" width="16" height="16" fill="#dc2626" stroke="#991b1b" stroke-width="1"/>
      <path fill="white" d="M8 4v2H6v2h2v2h2V8h2V6H10V4H8z"/>
    </svg>
  `),
  iconSize: [16, 16],
  iconAnchor: [8, 8],
  popupAnchor: [0, -8]
})

// Custom cluster component using native Leaflet clustering
const MarkerClusterLayer = ({ hospitals }) => {
  const map = useMap()
  const clusterGroupRef = useRef(null)

  const getStatusColor = (status) => {
    switch (status?.toLowerCase()) {
      case 'open': return '#22c55e'
      case 'closed': return '#ef4444'
      default: return '#6b7280'
    }
  }

  const formatBeds = (beds) => {
    if (!beds || beds === 0 || beds === -999) return 'Not specified'
    return beds.toString()
  }

  useEffect(() => {
    if (!map || !hospitals.length) return

    // Create cluster group
    const clusterGroup = L.markerClusterGroup({
      maxClusterRadius: 60,
      disableClusteringAtZoom: 15,
      spiderfyOnMaxZoom: true,
      showCoverageOnHover: false,
      zoomToBoundsOnClick: true,
      iconCreateFunction: (cluster) => {
        const count = cluster.getChildCount()
        let className = 'marker-cluster-small'

        if (count >= 100) {
          className = 'marker-cluster-large'
        } else if (count >= 10) {
          className = 'marker-cluster-medium'
        }

        return new L.DivIcon({
          html: `<div><span>${count}</span></div>`,
          className: `marker-cluster ${className}`,
          iconSize: new L.Point(40, 40)
        })
      }
    })

    // Add markers to cluster group
    hospitals.forEach((hospital) => {
      const marker = L.marker([hospital.latitude, hospital.longitude], {
        icon: hospitalIcon
      })

      const popupContent = `
        <div class="hospital-popup">
          <h3 style="margin: 0 0 8px 0; fontSize: 16px; color: #1f2937;">
            ${hospital.name}
          </h3>
          <div style="fontSize: 14px; lineHeight: 1.4;">
            <p style="margin: 4px 0;">
              <strong>Address:</strong><br />
              ${hospital.address}<br />
              ${hospital.city}, ${hospital.state} ${hospital.zip}
            </p>
            <p style="margin: 4px 0;">
              <strong>Type:</strong> ${hospital.type || 'Not specified'}
            </p>
            <p style="margin: 4px 0;">
              <strong>Status:</strong>
              <span style="color: ${getStatusColor(hospital.status)};">
                ${hospital.status || 'Unknown'}
              </span>
            </p>
            <p style="margin: 4px 0;">
              <strong>Beds:</strong> ${formatBeds(hospital.beds)}
            </p>
            ${hospital.telephone && hospital.telephone !== 'NOT AVAILABLE' ?
              `<p style="margin: 4px 0;">
                <strong>Phone:</strong> ${hospital.telephone}
              </p>` : ''
            }
            ${hospital.website && hospital.website !== 'NOT AVAILABLE' ?
              `<p style="margin: 4px 0;">
                <strong>Website:</strong>
                <a href="${hospital.website}" target="_blank" rel="noopener noreferrer" style="color: #3b82f6;">
                  Visit Site
                </a>
              </p>` : ''
            }
          </div>
        </div>
      `

      marker.bindPopup(popupContent, { maxWidth: 300 })
      clusterGroup.addLayer(marker)
    })

    // Add cluster group to map
    map.addLayer(clusterGroup)
    clusterGroupRef.current = clusterGroup

    // Cleanup function
    return () => {
      if (clusterGroupRef.current) {
        map.removeLayer(clusterGroupRef.current)
        clusterGroupRef.current = null
      }
    }
  }, [map, hospitals])

  return null
}

// Component to handle map navigation
const MapController = forwardRef((props, ref) => {
  const map = useMap()

  useImperativeHandle(ref, () => ({
    flyTo: (lat, lon, zoom = 10) => {
      map.flyTo([lat, lon], zoom, {
        duration: 1.5
      })
    }
  }), [map])

  return null
})

const HospitalMap = forwardRef(({ hospitals, loading }, ref) => {
  // Center map on continental US
  const center = [39.8283, -98.5795]
  const zoom = 4
  const mapControllerRef = useRef()

  useImperativeHandle(ref, () => ({
    flyTo: (lat, lon, zoom) => {
      mapControllerRef.current?.flyTo(lat, lon, zoom)
    }
  }), [])

  return (
    <div style={{ height: '100%', width: '100%' }}>
      <MapContainer
        center={center}
        zoom={zoom}
        style={{ height: '100%', width: '100%' }}
        zoomControl={true}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        <MapController ref={mapControllerRef} />
        {!loading && <MarkerClusterLayer hospitals={hospitals} />}
      </MapContainer>
    </div>
  )
})

export default HospitalMap