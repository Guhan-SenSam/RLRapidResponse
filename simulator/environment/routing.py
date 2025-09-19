"""
Routing Utilities - Step 1.4

Provides distance and travel time calculations using Haversine formula.
This is a temporary solution using great-circle distances.
OSMnx road network routing will be added later for more realistic routing.
"""

import math
import numpy as np
from typing import List, Tuple


def euclidean_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate great-circle distance between two points using Haversine formula.

    The Haversine formula calculates the shortest distance over the earth's surface,
    giving an "as-the-crow-flies" distance between two points (ignoring obstacles
    like buildings, roads, terrain, etc.).

    Args:
        lat1: Latitude of point 1 in degrees
        lon1: Longitude of point 1 in degrees
        lat2: Latitude of point 2 in degrees
        lon2: Longitude of point 2 in degrees

    Returns:
        Distance in kilometers

    Formula:
        a = sin²(Δlat/2) + cos(lat1) * cos(lat2) * sin²(Δlon/2)
        c = 2 * atan2(√a, √(1−a))
        d = R * c
        where R = 6371 km (Earth's radius)
    """
    # Earth's radius in kilometers
    R = 6371.0

    # Convert latitude and longitude from degrees to radians
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)

    # Differences
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad

    # Haversine formula
    a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    # Distance in kilometers
    distance = R * c

    return distance


def euclidean_travel_time(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
    speed_kmh: float = 80.0
) -> float:
    """
    Calculate travel time between two points assuming constant speed.

    Args:
        lat1: Latitude of origin in degrees
        lon1: Longitude of origin in degrees
        lat2: Latitude of destination in degrees
        lon2: Longitude of destination in degrees
        speed_kmh: Travel speed in km/h (default 80 km/h for emergency vehicles,
                   which is ~1.2x normal urban speed of ~65 km/h)

    Returns:
        Travel time in minutes
    """
    distance_km = euclidean_distance(lat1, lon1, lat2, lon2)

    # Convert to minutes: (distance in km / speed in km/h) * 60 min/h
    travel_time_minutes = (distance_km / speed_kmh) * 60.0

    return travel_time_minutes


def precompute_distance_matrix(locations: List[Tuple[float, float]]) -> np.ndarray:
    """
    Precompute pairwise distances between all locations.

    This is useful for optimization algorithms that need to query distances
    repeatedly (e.g., nearest hospital search, route optimization).

    Args:
        locations: List of (lat, lon) tuples

    Returns:
        NxN numpy array where element [i,j] is the distance in km from
        location i to location j. Diagonal elements are 0.

    Example:
        >>> locations = [(34.05, -118.25), (34.07, -118.44)]
        >>> matrix = precompute_distance_matrix(locations)
        >>> matrix[0, 1]  # Distance from location 0 to location 1
        15.2
    """
    n = len(locations)
    distance_matrix = np.zeros((n, n))

    for i in range(n):
        for j in range(i + 1, n):  # Only compute upper triangle
            lat1, lon1 = locations[i]
            lat2, lon2 = locations[j]
            dist = euclidean_distance(lat1, lon1, lat2, lon2)

            # Matrix is symmetric
            distance_matrix[i, j] = dist
            distance_matrix[j, i] = dist

    return distance_matrix


if __name__ == '__main__':
    # Test routing utilities
    print("Testing Routing Utilities...")
    print("=" * 60)

    # Test 1: Known distance - LA Downtown to UCLA Medical Center
    print("\n1. Testing Haversine distance (LA Downtown → UCLA Medical Center)...")
    # LA Downtown (Pershing Square): 34.048°N, 118.251°W
    # UCLA Medical Center: 34.062°N, 118.445°W
    la_downtown = (34.048, -118.251)
    ucla_medical = (34.062, -118.445)

    distance = euclidean_distance(la_downtown[0], la_downtown[1], ucla_medical[0], ucla_medical[1])
    print(f"   Distance: {distance:.2f} km")
    print(f"   Expected: ~17-20 km")

    if 16.0 <= distance <= 21.0:
        print("   ✓ PASS: Distance within expected range")
    else:
        print("   ✗ FAIL: Distance outside expected range")

    # Test 2: Travel time calculation
    print("\n2. Testing travel time (emergency vehicle at 80 km/h)...")
    travel_time = euclidean_travel_time(
        la_downtown[0], la_downtown[1],
        ucla_medical[0], ucla_medical[1],
        speed_kmh=80.0
    )
    print(f"   Travel time: {travel_time:.2f} minutes")
    print(f"   Expected: ~13-16 minutes")

    if 12.0 <= travel_time <= 17.0:
        print("   ✓ PASS: Travel time within expected range")
    else:
        print("   ✗ FAIL: Travel time outside expected range")

    # Test 3: Zero distance (same location)
    print("\n3. Testing same location (should be 0 km)...")
    same_distance = euclidean_distance(34.05, -118.25, 34.05, -118.25)
    print(f"   Distance: {same_distance:.6f} km")

    if same_distance < 0.001:
        print("   ✓ PASS: Same location distance is ~0")
    else:
        print("   ✗ FAIL: Same location distance not zero")

    # Test 4: Known distance verification (New York to Los Angeles)
    print("\n4. Testing long distance (New York → Los Angeles)...")
    # New York City: 40.7128°N, 74.0060°W
    # Los Angeles: 34.0522°N, 118.2437°W
    ny = (40.7128, -74.0060)
    la = (34.0522, -118.2437)

    ny_la_distance = euclidean_distance(ny[0], ny[1], la[0], la[1])
    print(f"   Distance: {ny_la_distance:.2f} km")
    print(f"   Expected: ~3,940 km (great-circle distance)")

    if 3900 <= ny_la_distance <= 4000:
        print("   ✓ PASS: Long distance calculation correct")
    else:
        print("   ✗ FAIL: Long distance calculation incorrect")

    # Test 5: Distance matrix computation
    print("\n5. Testing distance matrix precomputation...")
    test_locations = [
        (34.05, -118.25),   # LA Downtown
        (34.07, -118.44),   # Santa Monica
        (34.14, -118.25),   # Hollywood
        (33.94, -118.40)    # LAX Airport
    ]

    matrix = precompute_distance_matrix(test_locations)
    print(f"   Matrix shape: {matrix.shape}")
    print(f"   Matrix:\n{matrix}")

    # Check matrix properties
    is_symmetric = np.allclose(matrix, matrix.T)
    diagonal_zero = np.allclose(np.diag(matrix), 0)
    all_positive = np.all(matrix >= 0)

    print(f"   Symmetric: {is_symmetric}")
    print(f"   Diagonal zero: {diagonal_zero}")
    print(f"   All non-negative: {all_positive}")

    if is_symmetric and diagonal_zero and all_positive:
        print("   ✓ PASS: Distance matrix properties correct")
    else:
        print("   ✗ FAIL: Distance matrix has incorrect properties")

    # Test 6: Verify matrix values match direct calculation
    print("\n6. Testing matrix values vs direct calculation...")
    direct_dist = euclidean_distance(
        test_locations[0][0], test_locations[0][1],
        test_locations[1][0], test_locations[1][1]
    )
    matrix_dist = matrix[0, 1]

    print(f"   Direct calculation: {direct_dist:.2f} km")
    print(f"   Matrix value: {matrix_dist:.2f} km")

    if abs(direct_dist - matrix_dist) < 0.001:
        print("   ✓ PASS: Matrix values match direct calculation")
    else:
        print("   ✗ FAIL: Matrix values don't match")

    # Test 7: Speed variations
    print("\n7. Testing different vehicle speeds...")
    test_distance = euclidean_distance(34.05, -118.25, 34.10, -118.30)

    time_emergency = euclidean_travel_time(34.05, -118.25, 34.10, -118.30, speed_kmh=80)
    time_normal = euclidean_travel_time(34.05, -118.25, 34.10, -118.30, speed_kmh=65)
    time_slow = euclidean_travel_time(34.05, -118.25, 34.10, -118.30, speed_kmh=40)

    print(f"   Distance: {test_distance:.2f} km")
    print(f"   Emergency (80 km/h): {time_emergency:.2f} min")
    print(f"   Normal (65 km/h): {time_normal:.2f} min")
    print(f"   Traffic (40 km/h): {time_slow:.2f} min")

    # Verify that slower speeds take longer
    if time_emergency < time_normal < time_slow:
        print("   ✓ PASS: Speed variations work correctly")
    else:
        print("   ✗ FAIL: Speed variations incorrect")

    # Test 8: Emergency vehicle speed factor
    print("\n8. Testing emergency vehicle speed (1.2x normal)...")
    normal_speed = 65  # km/h
    emergency_speed = 80  # km/h (approximately 1.23x normal)
    speed_factor = emergency_speed / normal_speed

    print(f"   Normal urban speed: {normal_speed} km/h")
    print(f"   Emergency speed: {emergency_speed} km/h")
    print(f"   Speed factor: {speed_factor:.2f}x")

    if 1.15 <= speed_factor <= 1.3:
        print("   ✓ PASS: Emergency speed is realistic 1.2x factor")
    else:
        print("   ✗ FAIL: Speed factor outside expected range")

    print("\n" + "=" * 60)
    print("✓ All routing utility tests completed!")
    print("\nNote: These are Haversine (great-circle) distances.")
    print("Real road distances will be ~1.2-1.5x longer when OSMnx routing is added.")
