from backend.database import db_manager
db_manager.connect()
total_c = db_manager.execute_query('SELECT count(*) as count FROM companies')
total_j = db_manager.execute_query('SELECT count(*) as count FROM job_postings')
print(f"Total Companies: {total_c}")
print(f"Total Jobs: {total_j}")
all_c = db_manager.execute_query('SELECT name FROM companies')
print(f"All names: {all_c}")
