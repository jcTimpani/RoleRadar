from backend.database import db_manager, CompanyOperations
import traceback

db_manager.connect()
company_ops = CompanyOperations(db_manager)

test_company = {
    "name": "TestCorp2",
    "industry": "Technology",
    "location_city": "Dallas",
    "location_state": "TX",
    "phone": "(214) 555-1234",
    "website": "https://testcorp2.com"
}

try:
    company_id = company_ops.create(test_company)
    print(f"Success! Created company with ID: {company_id}")
except Exception as e:
    print("-" * 60)
    traceback.print_exc()
    print("-" * 60)
