from flask import Flask, jsonify, request
from flask_cors import CORS
import pandas as pd
import os

app = Flask(__name__)
CORS(app)

# Global variable to store the hospital data
hospital_data = None


def load_hospital_data():
    """Load hospital data from CSV file"""
    global hospital_data
    if hospital_data is None:
        csv_path = (
            "/mnt/Dev/Projects/RLRapidResponse/datasets/us_hospital_locations.csv"
        )
        hospital_data = pd.read_csv(csv_path)

        # Clean and prepare the data
        hospital_data = hospital_data.dropna(subset=["LATITUDE", "LONGITUDE"])
        hospital_data["LATITUDE"] = pd.to_numeric(
            hospital_data["LATITUDE"], errors="coerce"
        )
        hospital_data["LONGITUDE"] = pd.to_numeric(
            hospital_data["LONGITUDE"], errors="coerce"
        )

        # Remove rows with invalid coordinates
        hospital_data = hospital_data.dropna(subset=["LATITUDE", "LONGITUDE"])

    return hospital_data


@app.route("/api/hospitals", methods=["GET"])
def get_hospitals():
    """Get all hospital data"""
    try:
        data = load_hospital_data()

        # Convert to list of dictionaries with only needed fields
        hospitals = []
        for _, row in data.iterrows():
            hospital = {
                "id": row.get("ID", ""),
                "name": row.get("NAME", ""),
                "address": row.get("ADDRESS", ""),
                "city": row.get("CITY", ""),
                "state": row.get("STATE", ""),
                "zip": row.get("ZIP", ""),
                "latitude": row["LATITUDE"],
                "longitude": row["LONGITUDE"],
                "type": row.get("TYPE", ""),
                "status": row.get("STATUS", ""),
                "beds": row.get("BEDS", 0)
                if pd.notna(row.get("BEDS")) and row.get("BEDS") != -999
                else 0,
                "telephone": row.get("TELEPHONE", ""),
                "website": row.get("WEBSITE", ""),
            }
            hospitals.append(hospital)

        return jsonify({"hospitals": hospitals, "total": len(hospitals)})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/hospitals/count", methods=["GET"])
def get_hospital_count():
    """Get total count of hospitals"""
    try:
        data = load_hospital_data()
        return jsonify({"count": len(data)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/hospitals/viewport", methods=["GET"])
def get_hospitals_in_viewport():
    """Get hospitals within a viewport bounding box with buffer"""
    try:
        # Get viewport bounds from query parameters
        north = float(request.args.get('north'))
        south = float(request.args.get('south'))
        east = float(request.args.get('east'))
        west = float(request.args.get('west'))

        # Optional buffer parameter (default 0.1 degrees ~11km)
        buffer = float(request.args.get('buffer', 0.1))

        # Add buffer to viewport bounds
        north_buffered = north + buffer
        south_buffered = south - buffer
        east_buffered = east + buffer
        west_buffered = west - buffer

        data = load_hospital_data()

        # Filter hospitals within the buffered viewport
        filtered_hospitals = data[
            (data['LATITUDE'] >= south_buffered) &
            (data['LATITUDE'] <= north_buffered) &
            (data['LONGITUDE'] >= west_buffered) &
            (data['LONGITUDE'] <= east_buffered)
        ]

        # Convert to list of dictionaries with only needed fields
        hospitals = []
        for _, row in filtered_hospitals.iterrows():
            hospital = {
                "id": row.get("ID", ""),
                "name": row.get("NAME", ""),
                "address": row.get("ADDRESS", ""),
                "city": row.get("CITY", ""),
                "state": row.get("STATE", ""),
                "zip": row.get("ZIP", ""),
                "latitude": row["LATITUDE"],
                "longitude": row["LONGITUDE"],
                "type": row.get("TYPE", ""),
                "status": row.get("STATUS", ""),
                "beds": row.get("BEDS", 0)
                if pd.notna(row.get("BEDS")) and row.get("BEDS") != -999
                else 0,
                "telephone": row.get("TELEPHONE", ""),
                "website": row.get("WEBSITE", ""),
            }
            hospitals.append(hospital)

        return jsonify({
            "hospitals": hospitals,
            "total": len(hospitals),
            "viewport": {
                "north": north,
                "south": south,
                "east": east,
                "west": west,
                "buffer": buffer
            }
        })

    except (TypeError, ValueError) as e:
        return jsonify({"error": "Invalid viewport parameters. Required: north, south, east, west (numbers)"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy"})


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=9000)
