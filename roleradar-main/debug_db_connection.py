from backend.database import db_manager
import sqlalchemy as sa
from sqlalchemy import text

db_manager.connect()
print("Engine:", db_manager.engine)
with db_manager.get_session() as session:
    res = session.execute(text("SELECT DATABASE()")).fetchone()
    print("Database:", res[0])
    
    res = session.execute(text("SHOW TABLES")).fetchall()
    print("Tables:", res)
    
    count = session.execute(text("SELECT count(*) FROM companies")).scalar()
    print("Company count:", count)
    
    if count > 0:
        names = session.execute(text("SELECT name FROM companies LIMIT 10")).fetchall()
        print("Names:", names)
