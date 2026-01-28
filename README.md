A robust Flask-based backend that integrates the MBTA V3 API and Google Maps Directions API to provide "human-centric" transit routing for the Boston area.

Unlike standard apps, this backend calculates whether a user can actually catch a train based on their personalized walking speed (slow, normal, or fast), filtering out "impossible" connections.

✨ Key Features
Smart Routing: Filters Google Directions results based on user walking speed and a 60-second "platform buffer."

Live Vehicle Tracking: Real-time GPS coordinates for all Red, Orange, Blue, and Green line trains.

Station & Predictions: Fetches all subway stops and live countdowns for arrivals/departures.

Service Alerts: Real-time data on delays, closures, and transit service changes.

Polyline Support: Decodes Google’s overview polylines into coordinate arrays for easy map rendering.

🛠️ Tech Stack
Language: Python 3.x

Framework: Flask

APIs: MBTA V3 API, Google Maps Directions API

Libraries: requests, flask-cors, polyline, datetime

🚀 Getting Started
1. Prerequisites
You will need API keys from both providers:

MBTA API Key (Free)

Google Cloud Console (Enable Directions API)

2. Installation
Bash
# Clone the repository
git clone https://github.com/your-username/boston-transit-api.git
cd boston-transit-api

# Install dependencies
pip install flask flask-cors requests polyline
3. Environment Variables
For security, it is recommended to set your API keys as environment variables:

Bash
export GOOGLE_DIRECTIONS_API_KEY='your_google_key'
export MBTA_API_KEY='your_mbta_key'
4. Running the Server
Bash
python app.py
The server will start on http://localhost:5001.

📡 API Endpoints
Transit Routing
POST /api/directions

Body: ```json { "origin": "Park St", "destination": "Harvard Square", "walking_speed": "slow" }

Logic: Calculates if the user can walk to the station before the train departs based on the walking_speed profile.

Live Data
GET /api/mbta/stations: Returns a list of all subway stations with lat/lng.

GET /api/mbta/vehicles: Returns real-time locations and bearings of all active trains.

GET /api/mbta/predictions/<stop_id>: Returns the next 5 arriving trains for a specific stop.

GET /api/mbta/alerts: Returns active service disruptions.

🧠 Custom Logic: The Catchability Filter
The core "magic" of this API happens in the /api/directions route.

Speed Mapping: It converts labels (slow, normal, fast) into meters-per-second.

The Walk Check: It isolates the walking distance from the user's origin to the first transit stop.

The Buffer: If User Arrival Time > (Train Departure - 60 seconds), the route is discarded as "un-catchable," preventing the "running for a train you'll never catch" scenario.
