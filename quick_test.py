import requests
import json

def test_api():
    try:
        response = requests.get('http://localhost:8000/api/cost/usage/overall', timeout=5)
        print(f"✅ Status Code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ API Response: {json.dumps(data, indent=2)}")
        else:
            print(f"❌ Error: {response.text}")
    except requests.exceptions.ConnectionError:
        print("❌ Connection failed - Server may not be running")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_api()