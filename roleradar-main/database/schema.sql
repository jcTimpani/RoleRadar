-- Tech Company Web Crawler - Database Schema
-- MySQL Database: tech_jobs_db

-- Create database
CREATE DATABASE IF NOT EXISTS tech_jobs_db
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;

USE tech_jobs_db;

-- Companies Table
CREATE TABLE IF NOT EXISTS companies (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    website VARCHAR(500),
    industry VARCHAR(100),
    size VARCHAR(50),
    location_city VARCHAR(100),
    location_state VARCHAR(50),
    location_address TEXT,
    phone VARCHAR(50),
    hr_email VARCHAR(255),
    linkedin_url VARCHAR(500),
    description TEXT,
    logo_url VARCHAR(500),
    founded_year INT,
    rating DECIMAL(3, 2),
    reviews_count INT,
    last_crawled_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_industry (industry),
    INDEX idx_location (location_city, location_state),
    INDEX idx_name (name),
    UNIQUE KEY uk_website (website)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Job Postings Table
CREATE TABLE IF NOT EXISTS job_postings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    company_id INT,
    title VARCHAR(255) NOT NULL,
    department VARCHAR(100),
    location_city VARCHAR(100),
    location_state VARCHAR(50),
    location_remote BOOLEAN DEFAULT FALSE,
    job_type VARCHAR(50), -- full-time, part-time, contract, internship
    experience_level VARCHAR(50), -- entry, mid, senior, lead, executive
    salary_min DECIMAL(12, 2),
    salary_max DECIMAL(12, 2),
    salary_currency VARCHAR(10) DEFAULT 'USD',
    description TEXT,
    responsibilities TEXT,
    requirements TEXT,
    benefits TEXT,
    application_url VARCHAR(500),
    application_email VARCHAR(255),
    posted_date DATE,
    closing_date DATE,
    source VARCHAR(100), -- linkedin, indeed, glassdoor, company_website
    source_url TEXT,
    status ENUM('active', 'closed', 'draft', 'expired') DEFAULT 'active',
    scraped_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE SET NULL,
    INDEX idx_company (company_id),
    INDEX idx_title (title),
    INDEX idx_status (status),
    INDEX idx_posted_date (posted_date),
    INDEX idx_source (source),
    INDEX idx_location (location_city, location_state),
    INDEX idx_experience (experience_level)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Skills Table
CREATE TABLE IF NOT EXISTS skills (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    category VARCHAR(50),
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_category (category),
    INDEX idx_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Job-Skill Mapping Table
CREATE TABLE IF NOT EXISTS job_skills (
    id INT AUTO_INCREMENT PRIMARY KEY,
    job_id INT NOT NULL,
    skill_id INT NOT NULL,
    importance ENUM('required', 'preferred', 'nice_to_have') DEFAULT 'required',
    proficiency_level VARCHAR(50),
    years_experience INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES job_postings(id) ON DELETE CASCADE,
    FOREIGN KEY (skill_id) REFERENCES skills(id) ON DELETE CASCADE,
    UNIQUE KEY uk_job_skill (job_id, skill_id),
    INDEX idx_job (job_id),
    INDEX idx_skill (skill_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Education Requirements Table
CREATE TABLE IF NOT EXISTS education_levels (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    level INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Job-Education Mapping Table
CREATE TABLE IF NOT EXISTS job_education (
    id INT AUTO_INCREMENT PRIMARY KEY,
    job_id INT NOT NULL,
    education_id INT NOT NULL,
    is_required BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (job_id) REFERENCES job_postings(id) ON DELETE CASCADE,
    FOREIGN KEY (education_id) REFERENCES education_levels(id) ON DELETE CASCADE,
    UNIQUE KEY uk_job_education (job_id, education_id),
    INDEX idx_job (job_id),
    INDEX idx_education (education_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- HR Contacts Table
CREATE TABLE IF NOT EXISTS hr_contacts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    company_id INT,
    name VARCHAR(255),
    title VARCHAR(100),
    email VARCHAR(255),
    phone VARCHAR(50),
    linkedin_url VARCHAR(500),
    is_verified BOOLEAN DEFAULT FALSE,
    last_contacted_at TIMESTAMP NULL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE SET NULL,
    INDEX idx_company (company_id),
    INDEX idx_email (email),
    INDEX idx_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Crawler Logs Table
CREATE TABLE IF NOT EXISTS crawler_logs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    task_id VARCHAR(100),
    company_id INT,
    action VARCHAR(50),
    status ENUM('started', 'success', 'failed', 'skipped') DEFAULT 'success',
    message TEXT,
    error_details TEXT,
    duration_ms INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_task (task_id),
    INDEX idx_company (company_id),
    INDEX idx_status (status),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Interview Sessions Table
CREATE TABLE IF NOT EXISTS interview_sessions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    job_id INT,
    user_id VARCHAR(100),
    interview_type VARCHAR(50),
    questions_asked JSON,
    user_responses JSON,
    feedback JSON,
    overall_score DECIMAL(5, 2),
    duration_minutes INT,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP NULL,
    FOREIGN KEY (job_id) REFERENCES job_postings(id) ON DELETE SET NULL,
    INDEX idx_job (job_id),
    INDEX idx_user (user_id),
    INDEX idx_started_at (started_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Resumes Table
CREATE TABLE IF NOT EXISTS resumes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(100),
    filename VARCHAR(255),
    file_path VARCHAR(500),
    file_type VARCHAR(20),
    extracted_skills JSON,
    extracted_experience JSON,
    extracted_education JSON,
    overall_score DECIMAL(5, 2),
    analysis_notes TEXT,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user (user_id),
    INDEX idx_uploaded_at (uploaded_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Skill Gap Analysis Table
CREATE TABLE IF NOT EXISTS skill_gap_analysis (
    id INT AUTO_INCREMENT PRIMARY KEY,
    resume_id INT,
    job_id INT,
    matched_skills JSON,
    missing_skills JSON,
    skill_match_percentage DECIMAL(5, 2),
    recommendations JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (resume_id) REFERENCES resumes(id) ON DELETE CASCADE,
    FOREIGN KEY (job_id) REFERENCES job_postings(id) ON DELETE CASCADE,
    INDEX idx_resume (resume_id),
    INDEX idx_job (job_id),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Market Analytics Table
CREATE TABLE IF NOT EXISTS market_analytics (
    id INT AUTO_INCREMENT PRIMARY KEY,
    analysis_date DATE NOT NULL,
    metric_type VARCHAR(100),
    metric_value DECIMAL(15, 2),
    metric_count INT,
    category VARCHAR(100),
    city VARCHAR(100),
    state VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_analysis_date (analysis_date),
    INDEX idx_metric_type (metric_type),
    INDEX idx_category (category),
    INDEX idx_location (city, state)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Insert default education levels
INSERT INTO education_levels (name, level) VALUES
('High School', 1),
('Associate Degree', 2),
('Bachelor Degree', 3),
('Master Degree', 4),
('Doctorate/PhD', 5),
('MBA', 4),
('Professional Degree', 5)
ON DUPLICATE KEY UPDATE level=VALUES(level);

-- Insert common skills
INSERT INTO skills (name, category) VALUES
-- Programming Languages
('Python', 'programming_languages'),
('JavaScript', 'programming_languages'),
('Java', 'programming_languages'),
('C++', 'programming_languages'),
('C#', 'programming_languages'),
('Go', 'programming_languages'),
('Rust', 'programming_languages'),
('TypeScript', 'programming_languages'),
('Ruby', 'programming_languages'),
('PHP', 'programming_languages'),
('Swift', 'programming_languages'),
('Kotlin', 'programming_languages'),
('Scala', 'programming_languages'),
('R', 'programming_languages'),

-- Frameworks & Libraries
('React', 'frameworks_libraries'),
('Angular', 'frameworks_libraries'),
('Vue.js', 'frameworks_libraries'),
('Django', 'frameworks_libraries'),
('Flask', 'frameworks_libraries'),
('Spring Boot', 'frameworks_libraries'),
('Node.js', 'frameworks_libraries'),
('Express.js', 'frameworks_libraries'),
('Ruby on Rails', 'frameworks_libraries'),
('.NET', 'frameworks_libraries'),
('TensorFlow', 'frameworks_libraries'),
('PyTorch', 'frameworks_libraries'),
('scikit-learn', 'frameworks_libraries'),

-- Databases
('MySQL', 'databases'),
('PostgreSQL', 'databases'),
('MongoDB', 'databases'),
('Redis', 'databases'),
('Elasticsearch', 'databases'),
('Oracle', 'databases'),
('SQL Server', 'databases'),
('DynamoDB', 'databases'),
('Cassandra', 'databases'),

-- Cloud Platforms
('AWS', 'cloud_platforms'),
('Azure', 'cloud_platforms'),
('Google Cloud', 'cloud_platforms'),
('Docker', 'tools_technologies'),
('Kubernetes', 'tools_technologies'),
('Terraform', 'tools_technologies'),

-- Tools & Technologies
('Git', 'tools_technologies'),
('Jira', 'tools_technologies'),
('Confluence', 'tools_technologies'),
('CI/CD', 'tools_technologies'),
('Linux', 'tools_technologies'),

-- Soft Skills
('Communication', 'soft_skills'),
('Teamwork', 'soft_skills'),
('Problem Solving', 'soft_skills'),
('Leadership', 'soft_skills'),
('Time Management', 'soft_skills'),
('Analytical Skills', 'soft_skills')
ON DUPLICATE KEY UPDATE category=VALUES(category);


CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    password_hash VARCHAR(255) NOT NULL,
    email_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_users_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS auth_tokens (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    token_hash CHAR(64) NOT NULL,
    purpose VARCHAR(20) NOT NULL,
    expires_at DATETIME NOT NULL,
    used_at DATETIME NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_auth_token_hash (token_hash),
    INDEX idx_auth_user_purpose (user_id, purpose),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
