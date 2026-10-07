"""
Database connection and operations module
"""

import logging
import os
from typing import Optional, List, Dict, Any
from contextlib import contextmanager
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import QueuePool

import yaml

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Database connection manager"""
    
    def __init__(self):
        # Load config
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.yaml')
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)['database']
        # Hosted deployments supply credentials through the environment so no secret
        # ever needs to live in config.yaml. Unset variables leave config.yaml in charge.
        for key, var in (('host', 'DB_HOST'), ('port', 'DB_PORT'), ('username', 'DB_USER'),
                         ('password', 'DB_PASSWORD'), ('name', 'DB_NAME')):
            value = os.environ.get(var)
            if value:
                self.config[key] = int(value) if key == 'port' else value
        self.engine = None
        self.session_factory = None
    
    def connect(self):
        """Create database connection based on config type"""
        db_type = self.config.get('type', 'sqlite')
        
        if db_type == 'sqlite':
            db_path = self.config.get('path', 'D:/7/data/tech_jobs.db')
            # Ensure directory exists
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            connection_string = f"sqlite:///{db_path}"
            logger.info(f"Using SQLite database: {db_path}")
        else:
            # MySQL
            connection_string = (
                f"mysql+mysqlconnector://{self.config['username']}:{self.config['password']}"
                f"@{self.config['host']}:{self.config['port']}/{self.config['name']}"
            )
            logger.info(f"Using MySQL database: {self.config['name']}")
        
        connect_args = {}
        if db_type != 'sqlite' and os.environ.get('DB_SSL', '').lower() in ('1', 'true', 'yes'):
            # Managed MySQL (e.g. TiDB Cloud) requires TLS; verify against the system CA bundle.
            ca_path = os.environ.get('DB_SSL_CA', '/etc/ssl/certs/ca-certificates.crt')
            connect_args = {'ssl_disabled': False, 'ssl_verify_cert': True}
            if os.path.exists(ca_path):
                connect_args['ssl_ca'] = ca_path

        self.engine = create_engine(
            connection_string,
            poolclass=QueuePool,
            pool_size=int(os.environ.get('DB_POOL_SIZE', self.config.get('pool_size', 10))),
            max_overflow=int(os.environ.get('DB_MAX_OVERFLOW', self.config.get('max_overflow', 20))),
            pool_pre_ping=True,
            # Managed MySQL closes idle connections (TiDB Cloud after 30 minutes).
            pool_recycle=1500,
            connect_args=connect_args,
            echo=self.config.get('echo', False)
        )
        
        self.session_factory = scoped_session(
            sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        )
        
        logger.info("Database connection established")
        
        # Create tables if they don't exist
        self.create_tables()
    
    @contextmanager
    def get_session(self):
        """Get database session context"""
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            session.close()
    
    def execute_query(self, query: str, params: Dict = None) -> List[Dict]:
        """Execute a query and return results as list of dicts"""
        with self.get_session() as session:
            result = session.execute(text(query), params or {})
            if result.returns_rows:
                columns = result.keys()
                return [dict(zip(columns, row)) for row in result.fetchall()]
            return []
    
    def execute_single(self, query: str, params: Dict = None) -> Optional[Dict]:
        """Execute query and return single result"""
        results = self.execute_query(query, params)
        return results[0] if results else None
    
    def execute_insert(self, query: str, params: Dict = None) -> int:
        """Execute INSERT query and return the last inserted ID"""
        with self.get_session() as session:
            result = session.execute(text(query), params or {})
            session.commit()
            # For SQLite, use lastrowid
            if hasattr(result, 'lastrowid') and result.lastrowid:
                return result.lastrowid
            # For other databases, try to get the inserted ID
            try:
                # Try to get the last inserted ID using a separate query for SQLite
                cursor = session.execute(text("SELECT last_insert_rowid()"))
                return cursor.scalar() or result.rowcount
            except:
                return result.rowcount
    
    def insert(self, table: str, data: Dict) -> int:
        """Insert a row and return the ID"""
        with self.get_session() as session:
            columns = ', '.join(data.keys())
            values = ', '.join([f':{k}' for k in data.keys()])
            result = session.execute(
                text(f"INSERT INTO {table} ({columns}) VALUES ({values})"),
                data
            )
            session.commit()
            return result.lastrowid
    
    def update(self, table: str, data: Dict, where: str, where_params: Dict) -> int:
        """Update rows and return affected count"""
        with self.get_session() as session:
            set_clause = ", ".join([f"{k} = :{k}" for k in data.keys()])
            params = {**data, **where_params}
            result = session.execute(
                text(f"UPDATE {table} SET {set_clause} WHERE {where}"),
                params
            )
            session.commit()
            return result.rowcount
    
    def close(self):
        """Close database connection"""
        if self.engine:
            self.engine.dispose()
            logger.info("Database connection closed")
    
    def create_tables(self):
        """Create database tables if they don't exist"""
        schema_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'database', 'schema.sql')
        
        with open(schema_path, 'r') as f:
            schema_sql = f.read()
        
        db_type = self.config.get('type', 'sqlite')
        
        # Split by semicolons and execute each statement
        raw_statements = schema_sql.split(';')
        statements = []
        for s in raw_statements:
            # Remove comments (lines starting with --)
            clean_lines = [line for line in s.split('\n') if not line.strip().startswith('--')]
            clean_s = '\n'.join(clean_lines).strip()
            if clean_s:
                statements.append(clean_s)
        
        with self.get_session() as session:
            for statement in statements:
                if statement:
                    try:
                        if db_type == 'mysql':
                            # For MySQL, run as is (maybe skip CREATE DATABASE/USE if already connected to it)
                            if statement.upper().startswith('CREATE DATABASE') or statement.upper().startswith('USE'):
                                continue
                            session.execute(text(statement))
                            session.commit()
                            continue
                            
                        # For SQLite, we need to handle the schema differently
                        # Skip CREATE DATABASE and USE for SQLite
                        if statement.upper().startswith('CREATE DATABASE') or statement.upper().startswith('USE'):
                            continue
                        
                        # Convert MySQL-specific syntax to SQLite where needed
                        sqlite_stmt = statement
                        
                        # Remove ENGINE clause
                        sqlite_stmt = sqlite_stmt.replace('ENGINE=InnoDB', '')
                        sqlite_stmt = sqlite_stmt.replace('DEFAULT CHARSET=utf8mb4', '')
                        
                        # Convert AUTO_INCREMENT to AUTOINCREMENT
                        sqlite_stmt = sqlite_stmt.replace('AUTO_INCREMENT', 'AUTOINCREMENT')
                        
                        # Handle TINYINT(1) and BOOLEAN as INTEGER
                        sqlite_stmt = sqlite_stmt.replace('TINYINT(1)', 'INTEGER')
                        sqlite_stmt = sqlite_stmt.replace('BOOLEAN', 'INTEGER')
                        
                        # Convert ENUM to TEXT
                        import re
                        sqlite_stmt = re.sub(r"ENUM\([^)]+\)", "TEXT", sqlite_stmt)
                        
                        # Remove ON DUPLICATE KEY UPDATE (MySQL specific)
                        sqlite_stmt = re.sub(r"ON DUPLICATE KEY UPDATE.*", "", sqlite_stmt, flags=re.IGNORECASE)
                        
                        # Handle INDEX and KEY inside CREATE TABLE
                        # Remove lines starting with INDEX (SQLite creates indexes separately)
                        lines = sqlite_stmt.split('\n')
                        clean_stmt_lines = []
                        for line in lines:
                            stripped = line.strip()
                            # Skip INDEX lines
                            if stripped.upper().startswith('INDEX '):
                                continue
                            # Convert UNIQUE KEY to UNIQUE
                            if stripped.upper().startswith('UNIQUE KEY '):
                                # Convert "UNIQUE KEY name (col)" to "CONSTRAINT name UNIQUE (col)"
                                match = re.match(r"UNIQUE KEY\s+(\w+)\s*(\(.*\))", stripped, re.IGNORECASE)
                                if match:
                                    clean_stmt_lines.append(f"CONSTRAINT {match.group(1)} UNIQUE {match.group(2)}" + ("," if stripped.endswith(",") else ""))
                                else:
                                    # Just standard unique
                                    clean_stmt_lines.append(line.replace('UNIQUE KEY', 'UNIQUE'))
                                continue
                            
                            clean_stmt_lines.append(line)
                        
                        sqlite_stmt = '\n'.join(clean_stmt_lines)
                        
                        # Cleanup trailing commas before closing parenthesis
                        # This avoids "near ")": syntax error"
                        sqlite_stmt = re.sub(r",\s*\)", ")", sqlite_stmt)
                        
                        print(f"DEBUG SQL: {sqlite_stmt}")
                        
                        session.execute(text(sqlite_stmt))
                        session.commit()
                    except Exception as e:
                        # Table might already exist, that's okay
                        session.rollback()
                        logger.debug(f"Statement execution note: {e}")
        
        logger.info("Database tables created/verified")


# Company operations
class CompanyOperations:
    """Database operations for companies"""
    
    def __init__(self, db: DatabaseManager):
        self.db = db
    
    def create(self, company_data: Dict) -> int:
        """Create a new company"""
        query = """
            INSERT INTO companies (
                name, website, industry, size, location_city,
                location_state, phone, hr_email, linkedin_url, description, logo_url
            ) VALUES (
                :name, :website, :industry, :size, :location_city,
                :location_state, :phone, :hr_email, :linkedin_url, :description, :logo_url
            )
        """
        full_data = {
            "name": company_data.get('name'),
            "website": company_data.get('website'),
            "industry": company_data.get('industry'),
            "size": company_data.get('size'),
            "location_city": company_data.get('location_city'),
            "location_state": company_data.get('location_state'),
            "phone": company_data.get('phone'),
            "hr_email": company_data.get('hr_email'),
            "linkedin_url": company_data.get('linkedin_url'),
            "description": company_data.get('description'),
            "logo_url": company_data.get('logo_url')
        }
        
        # Check if exists first — by name, then by website (both are UNIQUE in the schema,
        # so two records with different name strings but the same website would otherwise
        # throw an IntegrityError on insert and silently drop the job).
        check_query = "SELECT id FROM companies WHERE name = :name"
        existing = self.db.execute_single(check_query, {"name": full_data["name"]})
        if existing:
            return existing['id']

        if full_data["website"]:
            check_website_query = "SELECT id FROM companies WHERE website = :website"
            existing = self.db.execute_single(check_website_query, {"website": full_data["website"]})
            if existing:
                return existing['id']

        return self.db.execute_insert(query, full_data)
    
    def get_by_id(self, company_id: int) -> Optional[Dict]:
        """Get company by ID"""
        return self.db.execute_single(
            "SELECT * FROM companies WHERE id = :id",
            {"id": company_id}
        )
    
    def search(self, city: str = None, industry: str = None, 
               limit: int = 50, offset: int = 0) -> List[Dict]:
        """Search companies with filters"""
        conditions = []
        params = {}
        
        if city:
            conditions.append("location_city = :city")
            params["city"] = city
        if industry:
            conditions.append("industry = :industry")
            params["industry"] = industry
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        query = f"""
            SELECT * FROM companies 
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :offset
        """
        params["limit"] = limit
        params["offset"] = offset
        
        return self.db.execute_query(query, params)
    
    def update_last_crawled(self, company_id: int):
        """Update last crawled timestamp"""
        self.db.execute_query(
            "UPDATE companies SET last_crawled_at = NOW() WHERE id = :id",
            {"id": company_id}
        )


# Job operations
class JobOperations:
    """Database operations for job postings"""
    
    def __init__(self, db: DatabaseManager):
        self.db = db
    
    def create(self, job_data: Dict) -> int:
        """Create a new job posting with defaults for optional fields"""
        from datetime import datetime
        import re

        # Provide defaults for required fields
        remote_val = job_data.get('remote_policy')
        is_remote = 1 if remote_val and 'remote' in str(remote_val).lower() else 0

        # salary_min/salary_max win if given directly; otherwise parse a "$130K - $180K"
        # style salary_range string (accepted for backwards compatibility with callers
        # that don't know the underlying columns are split min/max).
        salary_min = job_data.get('salary_min')
        salary_max = job_data.get('salary_max')
        if (salary_min is None or salary_max is None) and job_data.get('salary_range'):
            nums = re.findall(r'([\d,]+)\s*K', str(job_data['salary_range']), flags=re.IGNORECASE)
            if len(nums) >= 2:
                salary_min = salary_min if salary_min is not None else int(nums[0].replace(',', '')) * 1000
                salary_max = salary_max if salary_max is not None else int(nums[1].replace(',', '')) * 1000

        defaults = {
            'company_id': job_data.get('company_id'),
            'title': job_data.get('title'),
            'department': job_data.get('department'),
            'location_remote': is_remote,
            'description': job_data.get('description'),
            'requirements': job_data.get('requirements'),
            'source_url': job_data.get('source_url'),
            'source': job_data.get('source_type') or 'crawler',
            'job_type': job_data.get('job_type') or 'full-time',
            'experience_level': job_data.get('experience_level'),
            'location_city': job_data.get('location_city'),
            'location_state': job_data.get('location_state') or 'TX',
            'posted_date': job_data.get('posted_date') or datetime.utcnow().strftime('%Y-%m-%d'),
            'salary_min': salary_min,
            'salary_max': salary_max,
        }

        # Check for duplicates by source_url
        if defaults['source_url']:
            check_query = "SELECT id FROM job_postings WHERE source_url = :source_url"
            existing = self.db.execute_single(check_query, {"source_url": defaults["source_url"]})
            if existing:
                return existing['id']

        query = """
            INSERT INTO job_postings (
                company_id, title, department, location_city, location_state,
                job_type, experience_level, location_remote,
                description, requirements, source_url, source, posted_date,
                salary_min, salary_max
            ) VALUES (
                :company_id, :title, :department, :location_city, :location_state,
                :job_type, :experience_level, :location_remote,
                :description, :requirements, :source_url, :source, :posted_date,
                :salary_min, :salary_max
            )
        """
        return self.db.execute_insert(query, defaults)
    
    def get_by_id(self, job_id: int) -> Optional[Dict]:
        """Get job by ID with company info"""
        query = """
            SELECT j.*, c.name as company_name, c.website as company_website
            FROM job_postings j
            LEFT JOIN companies c ON j.company_id = c.id
            WHERE j.id = :id
        """
        return self.db.execute_single(query, {"id": job_id})
    
    def search(self, filters: Dict) -> List[Dict]:
        """Search jobs with filters"""
        conditions = []
        params = {}
        
        if filters.get('city'):
            conditions.append("j.location_city = :city")
            params["city"] = filters['city']
        if filters.get('state'):
            conditions.append("j.location_state = :state")
            params["state"] = filters['state']
        if filters.get('experience_level'):
            conditions.append("j.experience_level = :experience_level")
            params["experience_level"] = filters['experience_level']
        if filters.get('job_type'):
            conditions.append("j.job_type = :job_type")
            params["job_type"] = filters['job_type']
        if filters.get('remote_only'):
            conditions.append("j.location_remote = 1")
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        query = f"""
            SELECT j.*, c.name as company_name
            FROM job_postings j
            LEFT JOIN companies c ON j.company_id = c.id
            WHERE {where_clause}
            ORDER BY j.posted_date DESC
            LIMIT :limit OFFSET :offset
        """
        params["limit"] = filters.get('per_page', 20)
        params["offset"] = (filters.get('page', 1) - 1) * params["limit"]
        
        return self.db.execute_query(query, params)
    
    def add_skill(self, job_id: int, skill_id: int, importance: str = 'required'):
        """Add skill to job posting"""
        query = """
            INSERT INTO job_skills (job_id, skill_id, importance)
            VALUES (:job_id, :skill_id, :importance)
            ON DUPLICATE KEY UPDATE importance = :importance
        """
        self.db.execute_query(query, {
            "job_id": job_id, 
            "skill_id": skill_id, 
            "importance": importance
        })
    
    def get_skills(self, job_id: int) -> List[Dict]:
        """Get skills for a job"""
        query = """
            SELECT s.*, js.importance, js.years_experience
            FROM skills s
            JOIN job_skills js ON s.id = js.skill_id
            WHERE js.job_id = :job_id
        """
        return self.db.execute_query(query, {"job_id": job_id})


# Analytics operations
class AnalyticsOperations:
    """Database operations for analytics"""
    
    def __init__(self, db: DatabaseManager):
        self.db = db
    
    def get_job_count_by_skill(self, limit: int = 20) -> List[Dict]:
        """Get job count by skill"""
        query = """
            SELECT s.name, s.category, COUNT(js.id) as job_count
            FROM skills s
            JOIN job_skills js ON s.id = js.skill_id
            GROUP BY s.id
            ORDER BY job_count DESC
            LIMIT :limit
        """
        return self.db.execute_query(query, {"limit": limit})
    
    def get_salary_stats(self, city: str = None) -> Dict:
        """Get salary statistics"""
        conditions = ["salary_min > 0"]
        params = {}
        
        if city:
            conditions.append("location_city = :city")
            params["city"] = city
        
        where_clause = " AND ".join(conditions)
        
        query = f"""
            SELECT 
                AVG(salary_min) as avg_min,
                AVG(salary_max) as avg_max,
                MIN(salary_min) as min_salary,
                MAX(salary_max) as max_salary,
                COUNT(*) as total_jobs
            FROM job_postings
            WHERE {where_clause}
        """
        result = self.db.execute_single(query, params)
        
        if result:
            return {
                "average_min_salary": float(result['avg_min']) if result['avg_min'] else 0,
                "average_max_salary": float(result['avg_max']) if result['avg_max'] else 0,
                "total_jobs_with_salary": result['total_jobs']
            }
        return {}
    
    def get_job_trend(self, days: int = 30) -> List[Dict]:
        """Get job posting trend"""
        query = """
            SELECT 
                DATE(posted_date) as date,
                COUNT(*) as job_count
            FROM job_postings
            WHERE posted_date >= DATE_SUB(CURDATE(), INTERVAL :days DAY)
            GROUP BY DATE(posted_date)
            ORDER BY date
        """
        return self.db.execute_query(query, {"days": days})


# Initialize database and operations
db_manager = DatabaseManager()
company_ops = CompanyOperations(db_manager)
job_ops = JobOperations(db_manager)
analytics_ops = AnalyticsOperations(db_manager)


def init_database():
    """Initialize database connection"""
    db_manager.connect()


def close_database():
    """Close database connection"""
    db_manager.close()
