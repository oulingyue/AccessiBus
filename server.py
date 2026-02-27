from dotenv import load_dotenv
load_dotenv()
from flask import Flask, jsonify, request, Response
from flask_cors import CORS
import requests
import os
import polyline
from datetime import datetime, timedelta
 
app = Flask(__name__)
CORS(app)
 
GOOGLE_DIRECTIONS_API_KEY = os.getenv('GOOGLE_DIRECTIONS_API_KEY')
MBTA_API_KEY = os.getenv('MBTA_API_KEY')
ELEVENLABS_API_KEY = os.getenv('ELEVENLABS_API_KEY')
VOICE_ID = 'UgBBYS2sOqTuMpoF3BR0'
 
MBTA_BASE_URL = 'https://api-v3.mbta.com'
GOOGLE_BASE_URL = 'https://maps.googleapis.com/maps/api/directions/json'
 
def find_station_id(station_name):
    try:
        params = {'filter[route_type]': '0,1', 'api_key': MBTA_API_KEY}
        res = requests.get(f'{MBTA_BASE_URL}/stops', params=params).json()
        
        target = station_name.lower().replace(" station", "").strip()
        
        for stop in res['data']:
            stop_name = stop['attributes']['name'].lower().replace(" station", "").strip()
            if stop_name == target: return stop['id']
            if target in stop_name or stop_name in target: return stop['id']
                
    except Exception as e:
        print(f"Station Match Error: {e}")
    return None
 
@app.route('/api/mbta/stations', methods=['GET'])
def get_stations():
    try:
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
                desc = stop['attributes'].get('description', '')
                route = 'Green'
                if 'Red' in desc: route = 'Red'
                elif 'Orange' in desc: route = 'Orange'
                elif 'Blue' in desc: route = 'Blue'
                elif 'Mattapan' in desc: route = 'Red'
 
                wheelchair = stop['attributes'].get('wheelchair_boarding', 0)
                
                stations.append({
                    'id': stop['id'],
                    'name': stop['attributes']['name'],
                    'lat': stop['attributes']['latitude'],
                    'lng': stop['attributes']['longitude'],
                    'routes': [route],
                    'wheelchair_accessible': wheelchair == 1,
                    'has_parking': stop['attributes'].get('parking', False)
                })
            return jsonify({'success': True, 'data': stations})
        return jsonify({'success': False, 'data': []})
    except Exception as e:
        return jsonify({'success': False, 'data': []})
 
@app.route('/api/mbta/predictions/<stop_id>', methods=['GET'])
def get_predictions(stop_id):
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
                arrival = pred['attributes'].get('arrival_time')
                
                minutes = 0
                if arrival:
                    target_dt = datetime.fromisoformat(arrival.replace('Z', '+00:00'))
                    now = datetime.now(target_dt.tzinfo)
                    minutes = max(0, int((target_dt - now).total_seconds() / 60))
 
                direction_id = pred['attributes']['direction_id']
                destination = "Outbound" if direction_id == 0 else "Inbound"
                
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
        return jsonify({'success': False, 'data': []})
 
@app.route('/api/mbta/vehicles', methods=['GET'])
def get_vehicles():
    try:
        routes_filter = request.args.get('routes')
        if not routes_filter:
            return jsonify({'success': True, 'data': []})
 
        headers = {"x-api-key": MBTA_API_KEY}
        params = {'filter[route]': routes_filter, 'include': 'route'}
        
        response = requests.get(f'{MBTA_BASE_URL}/vehicles', params=params, headers=headers)
        
        if response.status_code == 200:
            raw_data = response.json()['data']
            vehicles = []
            for v in raw_data:
                if 'route' in v['relationships']:
                    route_id = v['relationships']['route']['data']['id']
                    occupancy = v['attributes'].get('occupancy_status', None)
                    
                    vehicles.append({
                        'id': v['id'],
                        'lat': v['attributes']['latitude'],
                        'lng': v['attributes']['longitude'],
                        'bearing': v['attributes']['bearing'],
                        'route': route_id,
                        'status': v['attributes']['current_status'],
                        'occupancy': occupancy
                    })
            return jsonify({'success': True, 'data': vehicles})
            
        return jsonify({'success': False, 'data': []})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/mbta/facilities/<stop_id>', methods=['GET'])
def get_facilities(stop_id):
    try:
        headers = {"x-api-key": MBTA_API_KEY}
        
        stop_res = requests.get(f'{MBTA_BASE_URL}/stops/{stop_id}', headers=headers)
        
        if stop_res.status_code == 200:
            stop_data = stop_res.json()
            parent_id = stop_id
            
            if 'relationships' in stop_data['data'] and 'parent_station' in stop_data['data']['relationships']:
                parent_data = stop_data['data']['relationships']['parent_station']['data']
                if parent_data:
                    parent_id = parent_data['id']
            
            params = {'filter[stop]': parent_id}
        else:
            params = {'filter[stop]': stop_id}
        
        response = requests.get(f'{MBTA_BASE_URL}/facilities', params=params, headers=headers)
        
        facilities = []
        if response.status_code == 200:
            data = response.json().get('data', [])
            
            for fac in data:
                attr = fac['attributes']
                fac_type = attr.get('type', 'UNKNOWN')
                
                if fac_type in ['ELEVATOR', 'ESCALATOR']:
                    facilities.append({
                        'id': fac['id'],
                        'type': fac_type,
                        'name': attr.get('short_name', 'Unknown'),
                        'long_name': attr.get('long_name', ''),
                        'operational': True
                    })
        
        return jsonify({'success': True, 'data': facilities})
        
    except Exception as e:
        print(f"Error fetching facilities: {e}")
        return jsonify({'success': False, 'data': []})
 
@app.route('/api/directions', methods=['POST'])
def get_directions():
    try:
        data = request.json
        origin_raw = data.get('origin')
        dest_raw = data.get('destination')
        speed_profile = data.get('walking_speed', 'normal')
 
        SPEED_MAP = {'slow': 0.9, 'normal': 1.4, 'fast': 1.8}
        user_speed = SPEED_MAP.get(speed_profile, 1.4)
 
        if isinstance(origin_raw, dict) and 'lat' in origin_raw:
            origin = f"{origin_raw['lat']},{origin_raw['lng']}"
        else:
            origin = f"{origin_raw}, Boston, MA"
 
        if isinstance(dest_raw, dict) and 'lat' in dest_raw:
            destination = f"{dest_raw['lat']},{dest_raw['lng']}"
        else:
            destination = f"{dest_raw}, Boston, MA"
 
        params = {
            'origin': origin,
            'destination': destination,
            'mode': 'transit',
            'transit_mode': 'subway',
            'alternatives': 'true',  
            'key': GOOGLE_DIRECTIONS_API_KEY
        }
        
        print(f"Google Search ({speed_profile}): {origin} -> {destination}")
        res = requests.get(GOOGLE_BASE_URL, params=params).json()
        print(f"Google Status: {res.get('status')}")
        
        if res['status'] == 'OK':
            valid_routes = []
            now = datetime.now()
 
            for i, route in enumerate(res['routes']):
                leg = route['legs'][0]
                
                route_confidence = 'high'
                route_warning = None
                total_walk_meters = 0
                first_station_name = "Destination"
                current_virtual_time = 0
                clean_steps = []
                transit_lines = []
 
                for step in leg['steps']:
                    step_points = polyline.decode(step['polyline']['points'])
                    step_path = [{'lat': p[0], 'lng': p[1]} for p in step_points]
                    
                    if step['travel_mode'] == 'WALKING':
                        walk_dist = step['distance']['value']
                        if current_virtual_time == 0: total_walk_meters += walk_dist
                        
                        clean_steps.append({
                            'instruction': step['html_instructions'],
                            'is_transit': False,
                            'path': step_path,
                            'mode': 'walking'
                        })
 
                    elif step['travel_mode'] == 'TRANSIT':
                        details = step.get('transit_details', {})
                        line_name = details.get('line', {}).get('name', 'Transit')
                        depart_stop = details.get('departure_stop', {}).get('name', 'Unknown Stop')
                        arrive_stop = details.get('arrival_stop', {}).get('name', 'Unknown Stop')
                        
                        step_duration_sec = step.get('duration', {}).get('value', 0)

                        if 'departure_time' in details:
                            this_depart_ts = details['departure_time']['value']
                        else:
                            this_depart_ts = current_virtual_time if current_virtual_time > 0 else int(now.timestamp())

                        if 'arrival_time' in details:
                            this_arrive_ts = details['arrival_time']['value']
                        else:
                            this_arrive_ts = this_depart_ts + step_duration_sec
                        
                        depart_id = find_station_id(depart_stop)
                        arrive_id = find_station_id(arrive_stop)

                        accessibility_text = []
                        try:
                            if depart_id:
                                stop_res = requests.get(f'{MBTA_BASE_URL}/stops/{depart_id}', headers={'x-api-key': MBTA_API_KEY})
                                if stop_res.status_code == 200:
                                    stop_data = stop_res.json()['data']
                                    wheelchair = stop_data['attributes'].get('wheelchair_boarding', 0)
                                    
                                    if wheelchair == 1:
                                        accessibility_text.append("Wheelchair accessible")
                                    
                                    parent_id = depart_id
                                    if 'relationships' in stop_data and 'parent_station' in stop_data['relationships']:
                                        parent_data = stop_data['relationships']['parent_station']['data']
                                        if parent_data:
                                            parent_id = parent_data['id']
                                    
                                    fac_res = requests.get(f'{MBTA_BASE_URL}/facilities', params={'filter[stop]': parent_id}, headers={'x-api-key': MBTA_API_KEY})
                                    if fac_res.status_code == 200:
                                        facilities = fac_res.json().get('data', [])
                                        elevator_count = sum(1 for f in facilities if f['attributes']['type'] == 'ELEVATOR')
                                        escalator_count = sum(1 for f in facilities if f['attributes']['type'] == 'ESCALATOR')
                                        
                                        if elevator_count > 0:
                                            accessibility_text.append(f"{elevator_count} elevator{'s' if elevator_count > 1 else ''}")
                                        if escalator_count > 0:
                                            accessibility_text.append(f"{escalator_count} escalator{'s' if escalator_count > 1 else ''}")
                        except Exception as e:
                            print(f"Accessibility fetch error: {e}")
                            
                        print(f"Step: {depart_stop}, Accessibility: {accessibility_text}")

                        if current_virtual_time == 0:
                            first_station_name = depart_stop
                            user_walk_seconds = int(total_walk_meters / user_speed)
                            user_arrival_ts = now.timestamp() + user_walk_seconds
                            
                            time_to_spare = this_depart_ts - user_arrival_ts
                            if time_to_spare < 0:
                                route_confidence = 'low'
                                route_warning = "Impossible: Departs before you arrive"
                            elif time_to_spare < 90:
                                route_confidence = 'medium'
                                route_warning = "Rush: Catching first train is tight"
                                
                        else:
                            prev_arrival_ts = current_virtual_time
                            transfer_gap = this_depart_ts - prev_arrival_ts
                            
                            if transfer_gap < 120:
                                if route_confidence != 'low':
                                    route_confidence = 'medium'
                                    route_warning = f"Tight Transfer at {depart_stop}"
                                if transfer_gap < 60:
                                    route_confidence = 'low'
                                    route_warning = f"Impossible Transfer at {depart_stop}"

                        current_virtual_time = this_arrive_ts
                        if line_name not in transit_lines: transit_lines.append(line_name)
                        
                        clean_steps.append({
                            'instruction': f"Take <b>{line_name}</b> from {depart_stop}",
                            'is_transit': True,
                            'departure_time': this_depart_ts,
                            'arrival_time': this_arrive_ts,
                            'stop_id': depart_id,
                            'dest_stop_id': arrive_id,
                            'station_name': depart_stop,
                            'path': step_path,
                            'line_name': line_name,
                            'mode': 'transit',
                            'accessibility_info': ", ".join(accessibility_text) if accessibility_text else None
                        })
                    else:
                        clean_steps.append({'instruction': step['html_instructions']})
 
                user_walk_seconds = int(total_walk_meters / user_speed)
                user_walk_minutes = int(user_walk_seconds / 60)
                user_arrival_at_station_dt = now + timedelta(seconds=user_walk_seconds)
                user_arrival_str = user_arrival_at_station_dt.strftime("%-I:%M %p")
                
                first_train_ts = next((s['departure_time'] for s in clean_steps if s.get('is_transit')), 0)
                train_depart_str = datetime.fromtimestamp(first_train_ts).strftime("%-I:%M %p") if first_train_ts else "N/A"
 
                route_summary = "Via " + " & ".join(transit_lines) if transit_lines else "Walking Route"
 
                path_points = []
                if 'overview_polyline' in route:
                    points = polyline.decode(route['overview_polyline']['points'])
                    path_points = [{'lat': p[0], 'lng': p[1]} for p in points]
 
                valid_routes.append({
                    'id': i,
                    'summary': route_summary,
                    'duration': leg['duration']['text'],
                    'time_range': f"Arr: {leg['arrival_time']['text']}",
                    'station_eta': f"Reach {first_station_name} by {user_arrival_str}",
                    'steps': clean_steps,
                    'path': path_points,
                    'catch_confidence': route_confidence,
                    'warning': route_warning,
                    'walk_minutes': f"{user_walk_minutes} min walk",
                    'user_arrival_time': user_arrival_str,
                    'train_departure_time': train_depart_str,
                })
 
            valid_routes.sort(key=lambda x: (1 if x['catch_confidence']=='high' else 2 if x['catch_confidence']=='medium' else 3, x['id']))
            print(f"Returning {len(valid_routes)} routes")
            return jsonify({'success': True, 'data': valid_routes[:5]})
        
        else:
            print(f"Google returned status: {res['status']}")
            return jsonify({'success': False, 'error': f"Google Error: {res['status']}"})
 
    except Exception as e:
        print(f"Server Error: {e}")
        return jsonify({'success': False, 'error': str(e)})
 
@app.route('/api/speak', methods=['GET', 'POST'])
def text_to_speech():
    try:
        text = request.args.get('text') or (request.json.get('text') if request.is_json else None)
        
        if not text:
            return jsonify({'success': False, 'error': 'No text provided'})
 
        if not ELEVENLABS_API_KEY:
            return jsonify({'success': False, 'error': 'ElevenLabs Key Missing'})
 
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": ELEVENLABS_API_KEY
        }
        payload = {
            "text": text,
            "model_id": "eleven_turbo_v2_5",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.5}
        }
 
        response = requests.post(url, json=payload, headers=headers)
 
        if response.status_code == 200:
            return Response(response.content, mimetype="audio/mpeg")
        else:
            print(f"ElevenLabs Failed: {response.status_code} - {response.text}")
            return jsonify({'success': False, 'error': response.text})
 
    except Exception as e:
        print(f"TTS Error: {e}")
        return jsonify({'success': False, 'error': str(e)})
 
if __name__ == '__main__':
    print("MBTA Backend Running on Port 5001...")
    app.run(debug=True, port=5001, host='0.0.0.0')