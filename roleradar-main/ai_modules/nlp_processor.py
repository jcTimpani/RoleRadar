"""
NLP-powered Job Requirement Extraction
Extracts and categorizes skills, experience levels, and qualifications
"""

import re
import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import spacy
from collections import Counter

from config import config

logger = logging.getLogger(__name__)


@dataclass
class JobRequirements:
    """Structured job requirements"""
    job_title: str = ""
    company_name: str = ""
    location: str = ""
    job_type: str = ""  # full-time, part-time, contract
    experience_level: str = ""  # entry, mid, senior, lead, executive
    experience_years_min: int = 0
    experience_years_max: int = 0
    skills_required: List[Dict[str, Any]] = None
    skills_preferred: List[Dict[str, Any]] = None
    education_required: str = ""
    education_preferred: str = ""
    responsibilities: List[str] = None
    qualifications: List[str] = None
    salary_min: int = 0
    salary_max: int = 0
    salary_currency: str = "USD"
    remote_policy: str = ""  # remote, hybrid, on-site
    benefits: List[str] = None
    
    def __post_init__(self):
        self.skills_required = self.skills_required or []
        self.skills_preferred = self.skills_preferred or []
        self.responsibilities = self.responsibilities or []
        self.qualifications = self.qualifications or []
        self.benefits = self.benefits or []


class SkillExtractor:
    """Extract and categorize skills from job descriptions"""
    
    def __init__(self, model: str = None):
        self.model = model or config['nlp']['model']
        try:
            self.nlp = spacy.load(self.model)
        except OSError:
            logger.warning(f"Spacy model {self.model} not found, downloading...")
            import subprocess
            subprocess.run(["python", "-m", "spacy", "download", self.model])
            self.nlp = spacy.load(self.model)
        
        self.skill_patterns = self._init_skill_patterns()
        self.skill_categories = config['nlp']['skill_categories']
        self.experience_mapping = config['nlp']['experience_mapping']
    
    def _init_skill_patterns(self) -> Dict[str, List[re.Pattern]]:
        """Initialize regex patterns for skill extraction"""
        return {
            'programming_languages': re.compile(
                r'\b(python|java(script)?|c\+\+|c#|go|rust|ruby|php|swift|kotlin|scala|typescript|perl|shell|bash|r|matlab|sas|sql)\b',
                re.I
            ),
            'frameworks_libraries': re.compile(
                r'\b(react|angular|vue|django|flask|spring|node\.?js|express|rails|\.net|tensorflow|pytorch|keras|scikit|opencv|jquery|bootstrap|tailwind)\b',
                re.I
            ),
            'databases': re.compile(
                r'\b(sql|mysql|postgresql|mongodb|redis|elasticsearch|oracle|sql server|mariadb|cassandra|dynamodb|firebase|neo4j|postgis)\b',
                re.I
            ),
            'cloud_platforms': re.compile(
                r'\b(aws|azure|gcp|google cloud|amazon web services|cloudflare|heroku|vercel|netlify|docker|kubernetes|k8s|terraform|ansible|puppet|chef)\b',
                re.I
            ),
            'tools_technologies': re.compile(
                r'\b(git|github|gitlab|bitbucket|jira|confluence|jenkins|ci/cd|devops|agile|scrum|linux|unix|macos|windows|docker compose|helm)\b',
                re.I
            ),
            'soft_skills': re.compile(
                r'\b(communication|teamwork|leadership|problem.?solving|analytical|time management|project management|interpersonal|stakeholder management)\b',
                re.I
            )
        }
    
    def extract_skills(self, text: str) -> Tuple[List[Dict], List[Dict]]:
        """Extract skills from job description text"""
        text_lower = text.lower()
        required_skills = []
        preferred_skills = []
        
        # Determine if skill is required or preferred
        is_required = bool(re.search(r'\b(required|must have|essential|minimum|necessary)\b', text_lower))
        is_preferred = bool(re.search(r'\b(preferred|nice to have|bonus|plus|desired|ideal)\b', text_lower))
        
        # Extract skills using patterns
        for category, pattern in self.skill_patterns.items():
            matches = pattern.findall(text)
            for match in matches:
                skill_name = match.strip() if isinstance(match, str) else match[0].strip()
                skill = {
                    'name': skill_name,
                    'category': category,
                    'source': 'pattern'
                }
                
                if is_required:
                    if skill not in required_skills:
                        required_skills.append(skill)
                elif is_preferred:
                    if skill not in preferred_skills:
                        preferred_skills.append(skill)
                else:
                    # Default to required if can't determine
                    if skill not in required_skills:
                        required_skills.append(skill)
        
        # Use NLP for additional skill extraction
        doc = self.nlp(text)
        for ent in doc.ents:
            if ent.label_ in ['ORG', 'PRODUCT', 'TECHNOLOGY']:
                skill = {
                    'name': ent.text,
                    'category': 'detected',
                    'source': 'nlp_entity'
                }
                if skill not in required_skills:
                    required_skills.append(skill)
        
        return required_skills, preferred_skills


class ExperienceExtractor:
    """Extract experience level and years from job descriptions"""
    
    def __init__(self):
        self.experience_mapping = config['nlp']['experience_mapping']
        self.years_pattern = re.compile(
            r'(\d+)\+?\s*(?:-|to)\s*(\d+)\+?\s*(?:years?|yrs?)?|'
            r'(?:minimum|at least|over)\s*(\d+)\s*(?:years?|yrs?)|'
            r'(\d+)\s*(?:-|to)\s*(\d+)\s*(?:years?|yrs?)|'
            r'(fresh|entry.?level|junior|mid.?level|senior|lead|principal|staff|director|vp|executive)',
            re.I
        )
    
    def extract_experience(self, text: str) -> Dict[str, Any]:
        """Extract experience requirements"""
        result = {
            'level': None,
            'years_min': 0,
            'years_max': 0
        }
        
        # Try to extract years
        match = self.years_pattern.search(text)
        if match:
            groups = match.groups()
            if any(groups[:2]):  # "X-Y years"
                result['years_min'] = int(groups[0] or groups[3] or 0)
                result['years_max'] = int(groups[1] or groups[4] or 0)
            elif groups[2]:  # "minimum X years"
                result['years_min'] = int(groups[2])
                result['years_max'] = result['years_min'] + 3
        
        # Extract level keywords
        text_lower = text.lower()
        for level, keywords in self.experience_mapping.items():
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    result['level'] = level
                    break
            if result['level']:
                break
        
        return result


class EducationExtractor:
    """Extract education requirements"""
    
    def __init__(self):
        self.education_patterns = {
            'high_school': re.compile(r'\b(high school|ged)\b', re.I),
            'associate': re.compile(r'\b(associate|2-year|diploma)\b', re.I),
            'bachelor': re.compile(r"\b(bachelor'?s?|b\.?s\.?|b\.?a\.?|undergraduate)\b", re.I),
            'master': re.compile(r"\b(master'?s?|m\.?s\.?|m\.?a\.?|mba)\b", re.I),
            'doctorate': re.compile(r'\b(ph\.?d\.?|doctorate|doctoral|md|jd)\b', re.I),
        }
        
        self.education_order = ['high_school', 'associate', 'bachelor', 'master', 'doctorate']
    
    def extract_education(self, text: str) -> Dict[str, Any]:
        """Extract education requirements"""
        result = {
            'required': None,
            'preferred': None,
            'exact_match': False
        }
        
        # Check for required education
        required_match = re.search(
            r'(?:required|minimum|must have|necessary).*?(high school|associate|bachelor|master|ph\.?d)',
            text, re.I
        )
        if required_match:
            found = required_match.group(1).lower()
            for level in self.education_order:
                if level in found:
                    result['required'] = level
                    break
        
        # Check for preferred education
        preferred_match = re.search(
            r'(?:preferred|desired|nice to have|ideal).*?(high school|associate|bachelor|master|ph\.?d)',
            text, re.I
        )
        if preferred_match:
            found = preferred_match.group(1).lower()
            for level in self.education_order:
                if level in found:
                    result['preferred'] = level
                    break
        
        # If no explicit requirement, assume bachelor's
        if not result['required']:
            result['required'] = 'bachelor'
        
        return result


class SalaryExtractor:
    """Extract salary information"""
    
    def __init__(self):
        self.salary_patterns = [
            # Patterns like "$80,000 - $120,000"
            re.compile(r'\$([\d,]+)\s*(?:-|to)\s*\$([\d,]+)'),
            # Patterns like "80k - 120k"
            re.compile(r'(\d+)[kK]\s*(?:-|to)\s*(\d+)[kK]'),
            # Patterns like "$80K per year"
            re.compile(r'\$([\d,]+)[kK]?\s*(?:per|a|annually|year|/year)'),
        ]
    
    def extract_salary(self, text: str) -> Dict[str, Any]:
        """Extract salary information"""
        result = {
            'salary_min': 0,
            'salary_max': 0,
            'currency': 'USD'
        }
        
        for pattern in self.salary_patterns:
            match = pattern.search(text)
            if match:
                groups = match.groups()
                try:
                    min_sal = int(groups[0].replace(',', ''))
                    max_sal = int(groups[1].replace(',', ''))
                    
                    # Normalize (handle k notation)
                    if min_sal < 1000:
                        min_sal *= 1000
                    if max_sal < 1000:
                        max_sal *= 1000
                    
                    result['salary_min'] = min_sal
                    result['salary_max'] = max_sal
                    break
                except (ValueError, IndexError):
                    continue
        
        return result


class RemotePolicyExtractor:
    """Extract remote work policy"""
    
    def extract_remote_policy(self, text: str) -> str:
        """Determine remote work policy"""
        text_lower = text.lower()
        
        if any(term in text_lower for term in ['remote', 'work from home', 'wfh', 'anywhere']):
            return 'remote'
        elif any(term in text_lower for term in ['hybrid', 'partially remote', '2-3 days']):
            return 'hybrid'
        elif any(term in text_lower for term in ['on-site', 'onsite', 'in-office', 'in office']):
            return 'on-site'
        else:
            return 'not specified'


class JobRequirementExtractor:
    """Main class to extract all job requirements"""
    
    def __init__(self):
        self.skill_extractor = SkillExtractor()
        self.experience_extractor = ExperienceExtractor()
        self.education_extractor = EducationExtractor()
        self.salary_extractor = SalaryExtractor()
        self.remote_extractor = RemotePolicyExtractor()
    
    def extract(self, job_description: str, job_url: str = "") -> JobRequirements:
        """Extract all requirements from a job description"""
        requirements = JobRequirements()
        
        # Basic job info extraction
        requirements.job_title = self._extract_title(job_description, job_url)
        
        # Extract skills
        required_skills, preferred_skills = self.skill_extractor.extract_skills(job_description)
        requirements.skills_required = required_skills
        requirements.skills_preferred = preferred_skills
        
        # Extract experience
        experience = self.experience_extractor.extract_experience(job_description)
        requirements.experience_level = experience['level']
        requirements.experience_years_min = experience['years_min']
        requirements.experience_years_max = experience['years_max']
        
        # Extract education
        education = self.education_extractor.extract_education(job_description)
        requirements.education_required = education['required']
        requirements.education_preferred = education['preferred']
        
        # Extract salary
        salary = self.salary_extractor.extract_salary(job_description)
        requirements.salary_min = salary['salary_min']
        requirements.salary_max = salary['salary_max']
        requirements.salary_currency = salary['currency']
        
        # Extract remote policy
        requirements.remote_policy = self.remote_extractor.extract_remote_policy(job_description)
        
        # Extract responsibilities and qualifications
        requirements.responsibilities = self._extract_list_items(job_description, 
                                                                  ['responsibilities', 'duties', 'what you will do'])
        requirements.qualifications = self._extract_list_items(job_description,
                                                                  ['qualifications', 'requirements', 'what you need'])
        
        return requirements
    
    def _extract_title(self, text: str, url: str) -> str:
        """Extract job title"""
        # Try to find title in first line or h1
        lines = text.split('\n')[:10]
        for line in lines:
            line = line.strip()
            if len(line) > 10 and len(line) < 200:
                # Look for common job title patterns
                if any(keyword in line.lower() for keyword in 
                       ['engineer', 'developer', 'manager', 'analyst', 'designer', 'architect']):
                    return line
        
        return ""
    
    def _extract_list_items(self, text: str, section_headers: List[str]) -> List[str]:
        """Extract bullet points from specific sections"""
        items = []
        text_lower = text.lower()
        
        # Find section
        for header in section_headers:
            header_pattern = rf'{header}[:\s]*(.*?)(?=\n\n|\n[A-Z]|\Z)'
            match = re.search(header_pattern, text, re.DOTALL | re.IGNORECASE)
            if match:
                section_text = match.group(1)
                # Extract bullet points
                bullets = re.findall(r'[•\-\*]\s*([^\n]+)', section_text)
                items = [b.strip() for b in bullets if len(b.strip()) > 10]
                break
        
        return items


def categorize_skill_gaps(user_skills: List[str], 
                          required_skills: List[Dict]) -> Dict[str, Any]:
    """Analyze skill gaps between user profile and job requirements"""
    user_skill_names = set(s.lower() for s in user_skills)
    
    missing_skills = []
    matched_skills = []
    
    for skill in required_skills:
        skill_name = skill['name'].lower()
        if skill_name in user_skill_names:
            matched_skills.append(skill)
        else:
            missing_skills.append(skill)
    
    match_percentage = len(matched_skills) / len(required_skills) * 100 if required_skills else 0
    
    # Generate learning recommendations
    recommendations = []
    for skill in missing_skills[:5]:  # Top 5 missing skills
        recommendations.append({
            'skill': skill['name'],
            'category': skill['category'],
            'learning_resources': f"Search for '{skill['name']} tutorial' or courses"
        })
    
    return {
        'matched_skills': matched_skills,
        'missing_skills': missing_skills,
        'match_percentage': round(match_percentage, 2),
        'recommendations': recommendations
    }


# Example usage
if __name__ == "__main__":
    # Sample job description
    sample_job = """
    Senior Software Engineer - Full Stack
    
    We are looking for a Senior Software Engineer to join our team.
    
    Required Skills:
    - Python (5+ years)
    - React.js (3+ years)
    - PostgreSQL
    - AWS experience
    - Docker and Kubernetes
    
    Preferred Skills:
    - Go programming
    - Machine learning experience
    
    Requirements:
    - Bachelor's degree in Computer Science or related field
    - 5+ years of software development experience
    - Strong communication skills
    
    We offer:
    - Remote work option
    - Competitive salary ($150,000 - $200,000)
    - Health insurance
    """
    
    extractor = JobRequirementExtractor()
    requirements = extractor.extract(sample_job)
    
    print("Job Requirements Extracted:")
    print(f"Experience Level: {requirements.experience_level}")
    print(f"Experience Years: {requirements.experience_years_min} - {requirements.experience_years_max}")
    print(f"Education Required: {requirements.education_required}")
    print(f"Salary Range: ${requirements.salary_min} - ${requirements.salary_max}")
    print(f"Remote Policy: {requirements.remote_policy}")
    print(f"\nRequired Skills ({len(requirements.skills_required)}):")
    for skill in requirements.skills_required:
        print(f"  - {skill['name']} ({skill['category']})")
