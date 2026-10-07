from backend.database import db_manager
import sqlalchemy as sa
from sqlalchemy import text

db_manager.connect()
with db_manager.get_session() as session:
    # Find jobs with duplicate source_url and keep only the one with lowest id
    query = """
    DELETE FROM job_postings 
    WHERE id NOT IN (
        SELECT id FROM (
            SELECT MIN(id) as id 
            FROM job_postings 
            GROUP BY source_url, company_id, title
        ) as tmp
    )
    """
    session.execute(text(query))
    session.commit()
    print("Duplicates removed.")
