from backend.database import db_manager, CompanyOperations

db_manager.connect()
db_manager.create_tables()

company_ops = CompanyOperations(db_manager)

test_company = {
    "name": "TestCorp",
    "industry": "Technology",
    "location_city": "Dallas",
    "location_state": "TX",
    "phone": "(214) 555-1234",
    "website": "https://testcorp.com"
}

try:
    company_id = company_ops.create(test_company)
    print(f"Success! Created company with ID: {company_id}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
