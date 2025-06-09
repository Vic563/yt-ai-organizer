#!/usr/bin/env python3
import requests
import json
import time

def test_cost_api():
    base_url = "http://localhost:8000/api/cost"
    
    endpoints = [
        "/usage/overall",
        "/usage/daily?days=7",
        "/usage/by-type",
        "/limits/check",
        "/pricing/info"
    ]
    
    print("Testing Cost Tracking API Endpoints...")
    print("=" * 50)
    
    for endpoint in endpoints:
        try:
            url = base_url + endpoint
            print(f"\nTesting: {url}")
            
            response = requests.get(url, timeout=5)
            print(f"Status Code: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"Response: {json.dumps(data, indent=2)}")
            else:
                print(f"Error: {response.text}")
                
        except requests.exceptions.ConnectionError:
            print(f"❌ Connection failed - Server may not be running")
            return False
        except Exception as e:
            print(f"❌ Error: {e}")
            
        time.sleep(0.5)  # Small delay between requests
    
    print("\n" + "=" * 50)
    print("✅ API testing completed!")
    return True

if __name__ == "__main__":
    test_cost_api()