from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import os
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)

# ============================================
# 1. CONFIGURATION & KEYS
# ============================================
# Ideally, keep these in a .env file. For now, we use defaults if env vars aren't set.
GOOGLE_DIRECTIONS_API_KEY = os.getenv('GOOGLE_DIRECTIONS_API_KEY', 'AIzaSyAG3UexynPg9bdaRbR5ATxhTuPyB5E64n4')
MBTA_API_KEY = os.getenv('MBTA_API_KEY', 'd0420e38428547f2b4e0da8ae04cf4b3')

MBTA_BASE_URL = 'https://api-v3.mbta.com'
GOOGLE_BASE_URL = 'https://maps.googleapis.com/maps/api/directions/json'

# ============================================
# 2. MBTA DATA ENDPOINTS
# ============================================

@app.route('/api/mbta/stations', methods=['GET'])
def get_stations():
    """
    Fetches all subway stations.
    The Frontend uses this list to calculate which one is closest to the user.
    """
    try:
        # Filter: 0=Light Rail (Green Line), 1=Subway (Red/Orange/Blue)
        params = {
            'filter[route_type]': '0,1',
            'api_key': MBTA_API_KEY,
            'include': 'parent_station'
        }
        response = requests.get(f'{MBTA_BASE_URL}/stops', params=params)
        
        if response.status_code == 200:
            data = response.json()['data']
            stations = []
            
            for stop in data:
                # Attempt to determine line color from description
                desc = stop['attributes'].get('description', '')
                route = 'Green' # Default fallback
                if 'Red' in desc: route = 'Red'
                elif 'Orange' in desc: route = 'Orange'
                elif 'Blue' in desc: route = 'Blue'
                elif 'Mattapan' in desc: route = 'Red'

                stations.append({
                    'id': stop['id'],
                    'name': stop['attributes']['name'],
                    'lat': stop['attributes']['latitude'],
                    'lng': stop['attributes']['longitude'],
                    'routes': [route] 
                })
            return jsonify({'success': True, 'data': stations})
        
        return jsonify({'success': False, 'data': []})
    except Exception as e:
        print(f"Error fetching stations: {e}")
        return jsonify({'success': False, 'data': []})

@app.route('/api/mbta/predictions/<stop_id>', methods=['GET'])
def get_predictions(stop_id):
    """
    Returns upcoming train times for a specific station.
    Example: "Red Line (Outbound) in 5 minutes"
    """
    try:
        headers = {"x-api-key": MBTA_API_KEY}
        params = {
            'filter[stop]': stop_id,
            'include': 'route',
            'sort': 'arrival_time',
            'page[limit]': 5
        }
        response = requests.get(f'{MBTA_BASE_URL}/predictions', params=params, headers=headers)
        
        predictions = []
        if response.status_code == 200:
            for pred in response.json()['data']:
                # Calculate minutes until arrival
                arrival = pred['attributes'].get('arrival_time')
                departure = pred['attributes'].get('departure_time')
                target_time = arrival or departure
                
                minutes = 0
                if target_time:
                    target_dt = datetime.fromisoformat(target_time.replace('Z', '+00:00'))
                    now = datetime.now(target_dt.tzinfo)
                    minutes = max(0, int((target_dt - now).total_seconds() / 60))

                # Determine direction
                direction_id = pred['attributes']['direction_id']
                destination = "Outbound" if direction_id == 0 else "Inbound"
                
                # Get Route Name (Red, Orange, etc)
                route_id = "Subway"
                if 'relationships' in pred and 'route' in pred['relationships']:
                    route_id = pred['relationships']['route']['data']['id']

                predictions.append({
                    'id': pred['id'],
                    'route': route_id,
                    'destination': destination,
                    'minutes': minutes,
                    'status': pred['attributes'].get('status', 'On Time')
                })
        return jsonify({'success': True, 'data': predictions})
    except Exception as e:
        print(f"Error predictions: {e}")
        return jsonify({'success': False, 'data': []})

@app.route('/api/mbta/alerts', methods=['GET'])
def get_alerts():
    """Returns active service alerts (delays, closures)"""
    try:
        params = {
            'filter[activity]': 'BOARD,RIDE',
            'filter[route_type]': '0,1',
            'api_key': MBTA_API_KEY
        }
        response = requests.get(f'{MBTA_BASE_URL}/alerts', params=params)
        
        if response.status_code == 200:
            raw_alerts = response.json()['data']
            alerts = []
            for item in raw_alerts:
                alerts.append({
                    'id': item['id'],
                    'header': item['attributes']['header'],
                    'description': item['attributes']['description'],
                    'severity': item['attributes']['severity']
                })
            return jsonify({'success': True, 'data': alerts})
        return jsonify({'success': False, 'data': []})
    except Exception as e:
        return jsonify({'success': False, 'data': []})

# ============================================
# 3. GOOGLE & UTILITY ENDPOINTS
# ============================================

# @app.route('/api/directions', methods=['POST'])
# def get_directions():
#     try:
#         data = request.json
#         origin_raw = data.get('origin')
#         dest_raw = data.get('destination')

#         # 1. Force context to Boston to fix "ZERO_RESULTS"
#         if isinstance(origin_raw, dict) and 'lat' in origin_raw:
#             origin = f"{origin_raw['lat']},{origin_raw['lng']}"
#         else:
#             origin = f"{origin_raw}, Boston, MA"

#         if isinstance(dest_raw, dict) and 'lat' in dest_raw:
#             destination = f"{dest_raw['lat']},{dest_raw['lng']}"
#         else:
#             destination = f"{dest_raw}, Boston, MA"

#         # 2. Call Google Maps (Transit Mode)
#         params = {
#             'origin': origin,
#             'destination': destination,
#             'mode': 'transit',
#             'transit_mode': 'subway', # Prefer subway over bus
#             'key': GOOGLE_DIRECTIONS_API_KEY
#         }
        
#         print(f"📡 Calling Google Maps: {origin} -> {destination}")
#         res = requests.get(GOOGLE_BASE_URL, params=params).json()
        
#         if res['status'] == 'OK':
#             leg = res['routes'][0]['legs'][0]
            
#             # --- NEW: INTELLIGENT PARSING OF MBTA DETAILS ---
#             clean_steps = []
            
#             for step in leg['steps']:
#                 instruction = step['html_instructions']
                
#                 # Case A: It is a Subway/Train ride
#                 if 'transit_details' in step:
#                     transit = step['transit_details']
#                     line_name = transit['line'].get('name', 'Transit')      # e.g. "Green Line E"
#                     vehicle_type = transit['line'].get('vehicle', {}).get('type', '')
#                     depart_stop = transit['departure_stop']['name']
#                     arrive_stop = transit['arrival_stop']['name']
#                     num_stops = transit.get('num_stops', 0)
                    
#                     # Create a rich, specific instruction
#                     clean_steps.append({
#                         'instruction': f"Board <b>{line_name}</b> at {depart_stop}"
#                     })
#                     clean_steps.append({
#                         'instruction': f"Ride {num_stops} stops to {arrive_stop}"
#                     })
                    
#                 # Case B: Walking / Transfers
#                 else:
#                     # If the instruction says "Walk", keep it simple
#                     clean_steps.append({'instruction': instruction})
@app.route('/api/directions', methods=['POST'])
def get_directions():
    try:
        data = request.json
        origin_raw = data.get('origin')
        dest_raw = data.get('destination')
        # speed_profile: 'slow', 'normal', 'fast' (Default to normal)
        speed_profile = data.get('walking_speed', 'normal') 

        # --- 1. DEFINE SPEEDS (Meters per Second) ---
        # Google avg is ~1.4 m/s (3.1 mph)
        SPEED_MAP = {
            'slow': 0.9,   # ~2.0 mph (Leisurely/Mobility issues)
            'normal': 1.4, # ~3.1 mph (Standard)
            'fast': 1.8    # ~4.0 mph (Brisk walk)
        }
        user_speed = SPEED_MAP.get(speed_profile, 1.4)

        if isinstance(origin_raw, dict) and 'lat' in origin_raw:
            origin = f"{origin_raw['lat']},{origin_raw['lng']}"
        else:
            origin = f"{origin_raw}, Boston, MA"

        if isinstance(dest_raw, dict) and 'lat' in dest_raw:
            destination = f"{dest_raw['lat']},{dest_raw['lng']}"
        else:
            destination = f"{dest_raw}, Boston, MA"

        # Ask Google for multiple alternatives
        params = {
            'origin': origin,
            'destination': destination,
            'mode': 'transit',
            'transit_mode': 'subway',
            'alternatives': 'true',  
            'key': GOOGLE_DIRECTIONS_API_KEY
        }
        
        print(f"📡 Google Search ({speed_profile}): {origin} -> {destination}")
        res = requests.get(GOOGLE_BASE_URL, params=params).json()
        
        if res['status'] == 'OK':
            valid_routes = []
            now = datetime.now()

            for i, route in enumerate(res['routes']):
                leg = route['legs'][0]
                
                # --- 2. ANALYZE WALKING SEGMENT ---
                total_walk_meters = 0
                first_station_name = "Destination"
                train_depart_timestamp = 0
                
                # Look through steps to find the walk BEFORE the train
                for step in leg['steps']:
                    if step['travel_mode'] == 'WALKING':
                        # Only count walking BEFORE we hit the train
                        if train_depart_timestamp == 0: 
                            total_walk_meters += step['distance']['value']
                    
                    elif step['travel_mode'] == 'TRANSIT':
                        # We found the train!
                        first_station_name = step['transit_details']['departure_stop']['name']
                        train_depart_timestamp = step['transit_details']['departure_time']['value']
                        break 
                
                # --- 3. CALCULATE USER'S REAL WALK TIME ---
                # Formula: Distance / Speed = Seconds
                user_walk_seconds = int(total_walk_meters / user_speed)
                
                # When does the user actually arrive at the platform?
                user_arrival_at_station_dt = now + timedelta(seconds=user_walk_seconds)
                user_arrival_timestamp = user_arrival_at_station_dt.timestamp()

                # --- 4. THE FILTER: IS IT CATCHABLE? ---
                # Only run this check if it involves a train (not a pure walking route)
                if train_depart_timestamp > 0:
                    # Buffer: User needs to arrive 60 seconds BEFORE train departs
                    if user_arrival_timestamp > (train_depart_timestamp - 60):
                        # print(f"❌ Route {i} IMPOSSIBLE: Arrive {user_arrival_at_station_dt} vs Depart {datetime.fromtimestamp(train_depart_timestamp)}")
                        continue # Skip this route, it's impossible to catch
                
                # --- 5. RECALCULATE ARRIVAL AT DESTINATION ---
                # Since user walk speed might be different from Google's, adjust the final arrival time
                original_duration = leg['duration']['value']
                google_expected_walk = total_walk_meters / 1.4
                delay_diff = user_walk_seconds - google_expected_walk
                
                real_arrival_val = now.timestamp() + original_duration + delay_diff
                real_duration_min = int((original_duration + delay_diff) / 60)
                
                # Format for UI
                station_eta_text = user_arrival_at_station_dt.strftime("%-I:%M %p")
                
                # Countdown Logic
                diff_min = int((datetime.fromtimestamp(train_depart_timestamp) - now).total_seconds() / 60)
                countdown_text = f"Departs in {diff_min} min" if diff_min > 0 else "Now"

                # Step Parsing
                clean_steps = []
                transit_lines = [] 
                for step in leg['steps']:
                    if 'transit_details' in step:
                        transit = step['transit_details']
                        line_name = transit['line'].get('name', 'Transit')
                        depart_stop = transit['departure_stop']['name']
                        num_stops = transit.get('num_stops', 0)
                        if line_name not in transit_lines: transit_lines.append(line_name)
                        clean_steps.append({'instruction': f"Board <b>{line_name}</b> at {depart_stop}"})
                        clean_steps.append({'instruction': f"Ride {num_stops} stops"})
                    else:
                        clean_steps.append({'instruction': step['html_instructions']})

                route_summary = "Via " + " & ".join(transit_lines) if transit_lines else "Walking Route"
                
                path_points = []
                if 'overview_polyline' in route:
                    import polyline 
                    points = polyline.decode(route['overview_polyline']['points'])
                    path_points = [{'lat': p[0], 'lng': p[1]} for p in points]

                valid_routes.append({
                    'id': i,
                    'sort_arrival': real_arrival_val, # We sort by when you get to the destination
                    'summary': route_summary,
                    'distance': leg['distance']['text'],
                    'duration': f"{real_duration_min} min",
                    'time_range': f"Leave Now – {(datetime.fromtimestamp(real_arrival_val)).strftime('%-I:%M %p')}",
                    'countdown': countdown_text,
                    'station_eta': f"Reach {first_station_name} by {station_eta_text}",
                    'steps': clean_steps,
                    'path': path_points
                })

            # Sort by Earliest Arrival at Destination
            valid_routes.sort(key=lambda x: x['sort_arrival'])
            
            # --- 6. RETURN TOP 3 ---
            return jsonify({'success': True, 'data': valid_routes[:3]})
        
        else:
            return jsonify({'success': False, 'error': f"Google Error: {res['status']}"})

    except Exception as e:
        print(f"Server Error: {e}")
        return jsonify({'success': False, 'error': str(e)})
    
@app.route('/api/favorites', methods=['GET', 'POST', 'DELETE'])
def handle_favorites():
    """
    STUB: Keeps the frontend happy without a database.
    Always returns empty success.
    """
    return jsonify({'success': True, 'data': []})


# to fetch the live positions of all subway trains.
@app.route('/api/mbta/vehicles', methods=['GET'])
def get_vehicles():
    """
    Fetches real-time locations of all active subway trains.
    """
    try:
        # We want all major subway lines
        routes = "Red,Orange,Blue,Green-B,Green-C,Green-D,Green-E"
        
        headers = {"x-api-key": MBTA_API_KEY}
        params = {
            'filter[route]': routes,
            'include': 'route' 
        }
        
        response = requests.get(f'{MBTA_BASE_URL}/vehicles', params=params, headers=headers)
        
        if response.status_code == 200:
            raw_data = response.json()['data']
            vehicles = []
            
            for v in raw_data:
                # Extract Line Name (Red, Orange, etc.)
                route_id = v['relationships']['route']['data']['id']
                
                vehicles.append({
                    'id': v['id'],
                    'lat': v['attributes']['latitude'],
                    'lng': v['attributes']['longitude'],
                    'bearing': v['attributes']['bearing'], # Direction (0-360 degrees)
                    'route': route_id,
                    'status': v['attributes']['current_status'] # STOPPED_AT, IN_TRANSIT_TO
                })
                
            return jsonify({'success': True, 'data': vehicles})
            
        return jsonify({'success': False, 'data': []})

    except Exception as e:
        print(f"Error fetching vehicles: {e}")
        return jsonify({
            'success': False, 
            'error': str(e),
            'message': 'Failed to fetch live vehicle data.'
        }), 500

if __name__ == '__main__':
    print("🚇 MBTA Backend Running on Port 5001...")
    app.run(debug=True, port=5001,host='0.0.0.0')