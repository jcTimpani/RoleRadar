import requests

# Sample companies
companies = [
    {"name": "AT&T", "industry": "Telecommunications", "location_city": "Dallas", "location_state": "TX", "phone": "(214) 555-0100", "website": "https://att.com"},
    {"name": "Toyota", "industry": "Automotive", "location_city": "Plano", "location_state": "TX", "phone": "(469) 555-0200", "website": "https://toyota.com"},
    {"name": "Southwest Airlines", "industry": "Airlines", "location_city": "Dallas", "location_state": "TX", "phone": "(214) 555-0300", "website": "https://southwest.com"},
    {"name": "Infosys", "industry": "IT Services", "location_city": "Plano", "location_state": "TX", "phone": "(972) 555-0400", "website": "https://infosys.com"},
    {"name": "Accenture", "industry": "Consulting", "location_city": "Irving", "location_state": "TX", "phone": "(214) 555-0500", "website": "https://accenture.com"},
]

# Create companies
for company in companies:
    response = requests.post("http://localhost:8000/api/companies", json=company)
    print(f"Created {company['name']}: {response.status_code}")

print("\nDatabase initialized successfully!")
