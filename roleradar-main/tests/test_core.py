"""
Unit tests for Tech Jobs Crawler
"""

import pytest
from ai_modules.nlp_processor import (
    JobRequirementExtractor, 
    SkillExtractor, 
    ExperienceExtractor
)


class TestSkillExtractor:
    """Tests for skill extraction"""
    
    def setup_method(self):
        self.extractor = SkillExtractor()
    
    def test_extract_python_skill(self):
        """Test Python skill extraction"""
        text = "We are looking for a Python developer with 5 years experience."
        required, preferred = self.extractor.extract_skills(text)
        skill_names = [s['name'].lower() for s in required]
        assert 'python' in skill_names
    
    def test_extract_multiple_skills(self):
        """Test extracting multiple skills"""
        text = "Required skills: Python, React, PostgreSQL, AWS, Docker"
        required, preferred = self.extractor.extract_skills(text)
        skill_names = [s['name'].lower() for s in required]
        assert len(skill_names) >= 3


class TestExperienceExtractor:
    """Tests for experience extraction"""
    
    def setup_method(self):
        self.extractor = ExperienceExtractor()
    
    def test_extract_years_experience(self):
        """Test extracting years of experience"""
        text = "We need someone with 3-5 years of experience in software development."
        result = self.extractor.extract_experience(text)
        assert result['years_min'] == 3
        assert result['years_max'] == 5
    
    def test_extract_senior_level(self):
        """Test extracting senior level"""
        text = "Looking for a senior software engineer with 5+ years experience."
        result = self.extractor.extract_experience(text)
        assert result['level'] == 'senior'


class TestJobRequirementExtractor:
    """Tests for job requirement extraction"""
    
    def setup_method(self):
        self.extractor = JobRequirementExtractor()
    
    def test_extract_full_job(self):
        """Test extracting requirements from full job description"""
        text = """
        Senior Software Engineer - TechCorp
        
        We are looking for a Senior Software Engineer to join our team.
        
        Requirements:
        - Bachelor's degree in Computer Science
        - 5+ years of software development experience
        - Python, React, PostgreSQL
        - AWS experience
        
        Salary: $150,000 - $200,000
        Remote work available
        """
        result = self.extractor.extract(text)
        
        assert result.experience_level == 'senior'
        assert result.experience_years_min >= 5
        assert len(result.skills_required) > 0
        assert result.remote_policy == 'remote'
    
    def test_extract_salary(self):
        """Test salary extraction"""
        text = "Competitive salary range: $120,000 - $180,000 per year"
        result = self.extractor.extract(text)
        assert result.salary_min == 120000
        assert result.salary_max == 180000


class TestCategorizeSkillGaps:
    """Tests for skill gap analysis"""
    
    def test_identify_missing_skills(self):
        """Test identifying missing skills"""
        from ai_modules.nlp_processor import categorize_skill_gaps
        
        user_skills = ['Python', 'JavaScript', 'SQL']
        job_skills = [
            {'name': 'Python', 'category': 'programming'},
            {'name': 'React', 'category': 'framework'},
            {'name': 'AWS', 'category': 'cloud'}
        ]
        
        result = categorize_skill_gaps(user_skills, job_skills)
        
        assert len(result['matched_skills']) == 1
        assert len(result['missing_skills']) == 2
        assert result['match_percentage'] > 0
        assert len(result['recommendations']) > 0


# Integration tests (require database)
@pytest.mark.integration
class TestDatabaseIntegration:
    """Integration tests for database operations"""
    
    def test_connection(self):
        """Test database connection"""
        from backend.database import db_manager
        try:
            db_manager.connect()
            assert db_manager.engine is not None
            db_manager.close()
        except Exception as e:
            pytest.skip(f"Database not available: {e}")


# Pytest configuration
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
