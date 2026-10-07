import requests
import time

API_BASE = "http://localhost:8000"

# 1. Check health
try:
    r = requests.get(f"{API_BASE}/health")
    print("Health:", r.json())
except:
    print("Server not reachable")

# 2. Get companies
r = requests.get(f"{API_BASE}/api/companies")
print("Companies Count:", len(r.json()))

# 3. Create a test company
test_company = {
    "name": "Validation Corp",
    "industry": "Validation",
    "location_city": "Dallas",
    "location_state": "TX",
    "website": "https://validation.com"
}
r = requests.post(f"{API_BASE}/api/companies", json=test_company)
print("Create Resp:", r.status_code, r.json())

# 4. Get again
r = requests.get(f"{API_BASE}/api/companies")
print("New Companies Count:", len(r.json()))
print("Names:", [c['name'] for c in r.json()])
