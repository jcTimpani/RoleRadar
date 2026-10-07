from backend.database import db_manager, JobOperations, CompanyOperations
import traceback

db_manager.connect()
company_ops = CompanyOperations(db_manager)
job_ops = JobOperations(db_manager)

# Use existing company ID (created in previous steps)
# AT&T should exist
existing = company_ops.search(limit=1)
if not existing:
    print("No companies found!")
    exit(1)

company_id = existing[0]['id']
print(f"Using company ID: {company_id}")

job_data = {
    "company_id": company_id,
    "title": "Debug Job",
    "description": "Debug description",
    "location_city": "Dallas",
    "location_state": "TX"
}

try:
    job_id = job_ops.create(job_data)
    print(f"Success! Created job with ID: {job_id}")
except Exception as e:
    print("-" * 60)
    traceback.print_exc()
    print("-" * 60)
