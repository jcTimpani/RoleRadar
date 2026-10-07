from backend.database import db_manager
db_manager.connect()
companies = db_manager.execute_query('SELECT id, name, phone FROM companies')
print(f"Total Companies in DB: {len(companies)}")
for c in companies[:5]:
    print(f"ID: {c['id']}, Name: {c['name']}, Phone: '{c['phone']}'")
