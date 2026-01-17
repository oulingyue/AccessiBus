import requests
import json

BASE_URL = "http://localhost:5001"

def test_health():
    """Test if the server is up"""
    print("Testing /api/health...", end=" ")
    try:
        response = requests.get(f"{BASE_URL}/api/health")
        if response.status_code == 200:
            print("✅ PASSED")
        else:
            print(f"❌ FAILED (Status: {response.status_code})")
    except Exception as e:
        print(f"❌ FAILED (Server not running?)")

def test_mbta_predictions():
    """Test getting live predictions for South Station"""
    print("Testing /api/mbta/predictions...", end=" ")
    params = {'stop_id': 'place-sstat'} # South Station ID
    response = requests.get(f"{BASE_URL}/api/mbta/predictions", params=params)
    
    if response.status_code == 200 and len(response.json()['data']) > 0:
        print("✅ PASSED")
    else:
        print(f"❌ FAILED (Response: {response.text})")

def test_google_directions():
    """Test the Google Maps integration"""
    print("Testing /api/directions...", end=" ")
    payload = {
        "origin": "South Station, Boston, MA",
        "destination": "Fenway Park, Boston, MA"
    }
    headers = {'Content-Type': 'application/json'}
    
    response = requests.post(f"{BASE_URL}/api/directions", json=payload, headers=headers)
    
    if response.status_code == 200 and 'routes' in response.json()['data']:
        print("✅ PASSED")
    else:
        print(f"❌ FAILED (Response: {response.text})")

if __name__ == "__main__":
    print("--- STARTING TESTS ---")
    test_health()
    test_mbta_predictions()
    test_google_directions()
    print("--- TESTS FINISHED ---")