from backend.database import db_manager
db_manager.connect()
companies = db_manager.execute_query('SELECT name, id FROM companies ORDER BY id DESC LIMIT 5')
jobs = db_manager.execute_query('SELECT title, company_id FROM job_postings ORDER BY id DESC LIMIT 5')
print("Recent Companies:", companies)
print("Recent Jobs:", jobs)
