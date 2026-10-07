# RoleRadar

> **Find jobs. Build skills. Get career ready.**

RoleRadar is a full-stack career preparation platform that combines **real job search**, **resume analysis**, **application tracking**, and **AI-powered interview practice** in one web application.

The platform is designed to support the entire job-search workflow — from finding an opportunity to preparing for the interview.

---

##  Features

###  Job Search

RoleRadar searches for current job listings using the **JSearch API through RapidAPI**.

Users can:

- Search by job title or keywords
- Search by location
- Filter job results
- View detailed job information
- View company information
- Open the original application page
- Find similar jobs
- Save jobs for later

The production job-search system uses JSearch rather than directly scraping major job boards.

---

###  Dashboard

The RoleRadar dashboard gives users a central view of their job-search progress.

It includes:

- Recommended jobs
- Application activity
- Resume analysis progress
- Interview practice progress
- Career-readiness checklist

---

###  Saved Jobs

Users can bookmark jobs and access them later from the **Saved Jobs** page.

> **Note:** Saved jobs are currently stored in browser `localStorage` and are not yet synchronized between devices.

---

###  Application Tracker

RoleRadar includes a lightweight application tracking system.

Applications can be organized into the following statuses:

| Status | Description |
| --- | --- |
| **Applied** | Application has been submitted |
| **Interviewing** | Interview process has started |
| **Offer** | An offer has been received |
| **Rejected** | Application has been closed or rejected |

Application data is currently stored locally in the user's browser.

---

###  AI Resume Checker

Users can upload a resume and compare it against either:

- A general target role
- A specific job listing

Supported file formats:

```text
.pdf
.docx
.txt
```

The resume checker can identify:

- Missing skills
- Missing experience or qualifications
- Areas that could be strengthened
- Resume completeness
- Role-specific gaps
- Potential improvements

AI-assisted resume analysis is powered by **Google Gemini**.

#### Supported Target Roles

Examples include:

- Software Engineer
- Backend Developer
- Frontend Developer
- Data Scientist
- Machine Learning Engineer
- DevOps / Cloud Engineer
- Cybersecurity Analyst
- QA / Test Automation Engineer

---

###  AI Interview Practice

RoleRadar generates interview questions based on a selected role or job listing.

Users can:

- Select a target position
- Choose a difficulty level
- Answer questions through text
- Use supported voice input
- Receive AI-generated feedback

Feedback can include:

- Technical accuracy
- Communication quality
- Relevant concepts and keywords
- Strengths
- Areas for improvement
- Suggested answer improvements

Interview question generation and feedback are powered by **Google Gemini**.

---

###  User Accounts

RoleRadar includes backend authentication with support for:

- Account creation
- Email verification
- Login
- Logout
- Persistent sessions
- Password changes
- Forgotten-password recovery
- Password reset
- Account deletion

Security features include:

- PBKDF2-HMAC-SHA256 password hashing
- Per-user password salts
- HTTP-only session cookies
- Hashed verification tokens
- Hashed password-reset tokens
- API rate limiting

Verification and password-reset emails can be sent through the **Brevo API**.

---

##  Technology Stack

### Frontend

- HTML5
- CSS3
- Vanilla JavaScript
- Font Awesome
- Browser `localStorage`
- Browser `sessionStorage`

### Backend

- Python
- FastAPI
- Uvicorn
- Pydantic
- SQLAlchemy
- HTTPX

### Database

- MySQL-compatible database
- MySQL Connector/Python
- SQLAlchemy connection pooling
- TiDB Cloud compatible

### AI

- Google Gemini API
- Custom interview practice logic
- Resume and skill-gap analysis
- Optional spaCy NLP tooling

### Job Data

- JSearch API
- RapidAPI

### Email

- Brevo API

### Deployment

- Render
- Python 3.12
- Uvicorn
- Automatic GitHub deployment

---

##  Project Structure

```text
RoleRadar/
│
├── README.md
│
└── roleradar-main/
    │
    ├── ai_modules/
    │   ├── interview_practice.py
    │   ├── jsearch_client.py
    │   ├── llm_client.py
    │   └── nlp_processor.py
    │
    ├── backend/
    │   ├── __init__.py
    │   ├── auth.py
    │   ├── database.py
    │   ├── guards.py
    │   └── main.py
    │
    ├── crawler/
    │   ├── distributed_crawler.py
    │   └── linkedin_crawler.py
    │
    ├── database/
    │   └── schema.sql
    │
    ├── frontend/
    │   ├── index.html
    │   ├── dashboard.html
    │   ├── find-jobs.html
    │   ├── job-details.html
    │   ├── saved-jobs.html
    │   ├── applications.html
    │   ├── resume-checker.html
    │   ├── interview-practice.html
    │   ├── login.html
    │   ├── profile.html
    │   ├── reset.html
    │   ├── verify.html
    │   └── assets/
    │       ├── css/
    │       ├── js/
    │       └── partials/
    │
    ├── config.yaml
    ├── render.yaml
    ├── requirements.txt
    └── requirements-render.txt
```

---

##  Architecture

RoleRadar is deployed as a single web service.

```text
                    ┌─────────────────────┐
                    │      Browser        │
                    │   HTML / CSS / JS   │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │      FastAPI        │
                    │       Uvicorn       │
                    └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
              ▼                ▼                ▼
       ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
       │ MySQL/TiDB  │  │   Gemini    │  │   JSearch   │
       │  Database   │  │     API     │  │  RapidAPI   │
       └─────────────┘  └─────────────┘  └─────────────┘
                               │
                               ▼
                        ┌─────────────┐
                        │    Brevo    │
                        │  Email API  │
                        └─────────────┘
```

FastAPI serves both the backend API and the files inside the `frontend/` directory.

This means RoleRadar does not require a separate frontend hosting service in production.

---

##  Database

The RoleRadar database contains tables for:

- Users
- Authentication tokens
- Companies
- Job postings
- Skills
- Job skills
- Education requirements
- HR contacts
- Resumes
- Skill-gap analysis
- Interview sessions
- Crawler logs
- Market analytics

The database schema is located at:

```text
roleradar-main/database/schema.sql
```

---
