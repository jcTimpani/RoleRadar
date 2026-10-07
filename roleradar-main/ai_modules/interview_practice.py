"""
AI Interview Practice System
Simulates role-specific interviews with speech-to-text and real-time feedback
"""

import asyncio
import json
import logging
import time
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from collections import deque
import re

from config import config
try:
    from .llm_client import LLMClient
except (ImportError, ValueError):
    try:
        from ai_modules.llm_client import LLMClient
    except ImportError:
        from llm_client import LLMClient

logger = logging.getLogger(__name__)

# Optional speech recognition - backend will work without it
try:
    import speech_recognition as sr
    SPEECH_RECOGNITION_AVAILABLE = True
except ImportError:
    logger.warning("speech_recognition not available - interview practice will use text input only")
    SPEECH_RECOGNITION_AVAILABLE = False
    sr = None


@dataclass
class InterviewQuestion:
    """Interview question with metadata"""
    question_id: str
    question_text: str
    category: str  # behavioral, technical, system_design, coding
    difficulty: str  # easy, medium, hard
    expected_keywords: List[str] = field(default_factory=list)
    sample_answer: str = ""
    tips: List[str] = field(default_factory=list)


@dataclass
class InterviewFeedback:
    """Feedback for interview response"""
    overall_score: float
    technical_accuracy: float
    communication_score: float
    filler_words_used: List[str]
    filler_word_count: int
    speaking_rate_wpm: float
    pacing_score: float
    strengths: List[str] = field(default_factory=list)
    improvements: List[str] = field(default_factory=list)
    suggested_answers: List[str] = field(default_factory=list)
    keywords_matched: List[str] = field(default_factory=list)
    keywords_missing: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)


class SpeechAnalyzer:
    """Analyze speech patterns for interview feedback"""
    
    def __init__(self):
        self.filler_words = {
            'english': [
                'um', 'uh', 'like', 'you know', 'sort of', 'kind of',
                'basically', 'actually', 'literally', 'so', 'right',
                'okay', 'well', 'i mean', 'at the end of the day'
            ]
        }
        self.word_timestamps = deque(maxlen=1000)
        self.filler_pattern = None
    
    def _build_filler_pattern(self):
        """Build regex pattern for filler words"""
        pattern = r'\b(' + '|'.join(self.filler_words['english']) + r')\b'
        self.filler_pattern = re.compile(pattern, re.I)
    
    def analyze_speech(self, transcript: str, audio_duration: float) -> Dict[str, Any]:
        """Analyze speech patterns"""
        if not self.filler_pattern:
            self._build_filler_pattern()
        
        # Count filler words
        filler_matches = self.filler_pattern.findall(transcript)
        filler_word_count = len(filler_matches)
        
        # Count total words
        words = transcript.split()
        word_count = len(words)
        
        # Calculate speaking rate
        speaking_rate = (word_count / audio_duration) * 60 if audio_duration > 0 else 0
        
        # Calculate filler word percentage
        filler_percentage = (filler_word_count / word_count * 100) if word_count > 0 else 0
        
        # Analyze pacing (variance in word timing would need audio analysis)
        # Using text-based heuristics for now
        avg_words_per_sentence = word_count / max(1, len(re.split(r'[.!?]', transcript)))
        
        return {
            'word_count': word_count,
            'filler_word_count': filler_word_count,
            'filler_words_used': list(set(m.lower() for m in filler_matches)),
            'filler_percentage': round(filler_percentage, 2),
            'speaking_rate_wpm': round(speaking_rate, 2),
            'avg_words_per_sentence': round(avg_words_per_sentence, 2),
            'transcript_length': len(transcript)
        }
    
    def evaluate_pacing(self, analysis: Dict[str, Any]) -> float:
        """Evaluate speaking pacing (0-100)"""
        rate = analysis['speaking_rate_wpm']
        
        # Ideal speaking rate is 120-150 WPM
        if 120 <= rate <= 150:
            return 100
        elif 100 <= rate <= 170:
            return 80
        elif 80 <= rate <= 190:
            return 60
        else:
            return 40


class KeywordAnalyzer:
    """Analyze keywords in interview responses"""
    
    def __init__(self):
        self.common_interview_keywords = {
            'technical': [
                'algorithm', 'data structure', 'complexity', 'o(n)', 'scalability',
                'api', 'database', 'framework', 'testing', 'deployment', 'ci/cd',
                'microservices', 'architecture', 'design pattern', 'optimization'
            ],
            'behavioral': [
                'team', 'collaborate', 'challenge', 'learned', 'difficult',
                'project', 'deadline', 'communication', 'leadership', 'initiative',
                'problem-solving', 'adaptable', 'growth', 'feedback', 'conflict'
            ],
            'leadership': [
                'mentor', 'guide', 'delegate', 'vision', 'strategy', 'stakeholder',
                'decision', 'ownership', 'accountability', 'inspire', 'motivate'
            ]
        }
    
    def analyze_keywords(self, transcript: str, question_type: str, expected_keywords: List[str] = None) -> Dict[str, Any]:
        """Analyze keywords in response"""
        transcript_lower = transcript.lower()
        
        # Priority should be given to question-specific keywords
        relevant_keywords = expected_keywords if expected_keywords else self.common_interview_keywords.get(question_type, [])
        
        matched = []
        missing = []
        
        for keyword in relevant_keywords:
            if keyword.lower() in transcript_lower:
                matched.append(keyword)
            else:
                missing.append(keyword)
        
        # Calculate keyword score
        keyword_score = (len(matched) / len(relevant_keywords) * 100) if relevant_keywords else 0
        
        return {
            'matched_keywords': matched,
            'missing_keywords': missing,
            'keyword_score': round(keyword_score, 2),
            'total_matched': len(matched),
            'total_relevant': len(relevant_keywords)
        }


class QuestionGenerator:
    """Generate interview questions based on job requirements"""
    
    def __init__(self):
        self.question_bank = self._load_question_bank()
    
    def _load_question_bank(self) -> Dict[str, List[InterviewQuestion]]:
        """Load interview questions from bank"""
        return {
            'behavioral': [
                InterviewQuestion(
                    'B001',
                    'Tell me about a time you faced a challenging technical problem. How did you solve it?',
                    'behavioral', 'medium',
                    expected_keywords=['problem', 'solution', 'steps', 'learned'],
                    tips=['Use STAR method: Situation, Task, Action, Result',
                         'Be specific about your role']
                ),
                InterviewQuestion(
                    'B002',
                    'Describe a situation where you had to work with a difficult team member.',
                    'behavioral', 'medium',
                    expected_keywords=['conflict', 'communication', 'resolution', 'collaboration'],
                    tips=['Focus on your actions and professionalism',
                         'Show how you turned a negative into positive']
                ),
                InterviewQuestion(
                    'B003',
                    'Tell me about a project you\'re most proud of and why.',
                    'behavioral', 'easy',
                    expected_keywords=['project', 'role', 'achievement', 'impact', 'skills'],
                    tips=['Highlight your specific contributions',
                         'Quantify results when possible']
                ),
                InterviewQuestion(
                    'B004',
                    'How do you handle tight deadlines when the workload is high?',
                    'behavioral', 'medium',
                    expected_keywords=['prioritize', 'time management', 'deadline', 'organization'],
                    tips=['Give specific examples',
                         'Show you remain calm under pressure']
                ),
            ],
            'technical': [
                InterviewQuestion(
                    'T001',
                    'Explain the difference between REST and GraphQL APIs.',
                    'technical', 'medium',
                    expected_keywords=['rest', 'graphql', 'api', 'endpoint', 'query', 'performance'],
                    tips=['Compare and contrast clearly',
                         'Mention use cases for each']
                ),
                InterviewQuestion(
                    'T002',
                    'How would you design a scalable URL shortening service?',
                    'technical', 'hard',
                    expected_keywords=['scalability', 'database', 'hash', 'collision', 'cache', 'architecture'],
                    tips=['Consider all components: API, storage, cache',
                         'Discuss trade-offs']
                ),
                InterviewQuestion(
                    'T003',
                    'What is dependency injection and why is it useful?',
                    'technical', 'medium',
                    expected_keywords=['dependency injection', 'loose coupling', 'testing', 'mocking'],
                    tips=['Give practical examples',
                         'Explain benefits for testing']
                ),
                InterviewQuestion(
                    'T004',
                    'Describe your approach to debugging a production issue.',
                    'technical', 'medium',
                    expected_keywords=['debug', 'logs', 'monitoring', 'reproduce', 'isolate', 'fix'],
                    tips=['Show systematic approach',
                         'Mention tools you use']
                ),
            ],
            'system_design': [
                InterviewQuestion(
                    'SD001',
                    'Design a notification system that can handle millions of messages per day.',
                    'system_design', 'hard',
                    expected_keywords=['queue', 'microservices', 'scalability', 'reliability', 'async'],
                    tips=['Consider scalability, fault tolerance',
                         'Discuss trade-offs between consistency and availability']
                ),
                InterviewQuestion(
                    'SD002',
                    'How would you design a real-time chat application like WhatsApp?',
                    'system_design', 'hard',
                    expected_keywords=['websocket', 'push notification', 'offline sync', 'encryption', 'scale'],
                    tips=['Cover core features and edge cases',
                         'Think about data consistency']
                ),
            ],
            'coding': [
                InterviewQuestion(
                    'C001',
                    'Given an array of integers, find the two numbers that add up to a specific target.',
                    'coding', 'easy',
                    expected_keywords=['array', 'hash map', 'two sum', 'complexity'],
                    tips=['Start with brute force, then optimize',
                         'Discuss time and space complexity']
                ),
                InterviewQuestion(
                    'C002',
                    'Implement a function to reverse a linked list.',
                    'coding', 'medium',
                    expected_keywords=['linked list', 'pointers', 'recursion', 'iteration'],
                    tips=['Draw the linked list',
                         'Handle edge cases']
                ),
            ]
        }
    
    def get_question(self, interview_type: str, difficulty: str = 'medium') -> InterviewQuestion:
        """Get a random question of given type and difficulty"""
        questions = self.question_bank.get(interview_type, [])
        filtered = [q for q in questions if q.difficulty == difficulty]
        if not filtered:
            filtered = questions
        return filtered[0] if filtered else None
    
    async def generate_questions_for_job(self, llm: LLMClient, job_requirements: Dict,
                                   role: str = "software_engineer",
                                   specific_job: bool = False,
                                   num_questions: int = 5,
                                   difficulty: str = "medium") -> List[InterviewQuestion]:
        """Generate role-specific and job-specific interview questions"""
        questions = []

        # Try AI generation first
        if llm.enabled:
            logger.info(f"Generating {difficulty}-difficulty interview questions using AI...")
            ai_data = await llm.generate_questions(role, job_requirements if specific_job else None, num_questions, difficulty)
            for q in ai_data:
                questions.append(InterviewQuestion(
                    question_id=q.get('id', f"AI_{int(time.time())}_{len(questions)}"),
                    question_text=q.get('question_text', ''),
                    category=q.get('category', 'technical'),
                    difficulty=q.get('difficulty', difficulty),
                    expected_keywords=q.get('expected_keywords', []),
                    sample_answer=q.get('sample_answer', ''),
                    tips=q.get('tips', [])
                ))

        # Fallback to bank if AI failed or is disabled
        if not questions:
            logger.info("Falling back to hardcoded question bank.")
            if specific_job:
                questions = self._generate_job_specific_questions(job_requirements)
            else:
                questions = self._generate_role_specific_questions(role)

            # Prefer questions matching the requested difficulty; the bank is small,
            # so fall back to the full set if nothing matches (mirrors get_question()).
            by_difficulty = [q for q in questions if q.difficulty == difficulty]
            if by_difficulty:
                questions = by_difficulty

            # Limit to requested number
            import random
            if len(questions) > num_questions:
                questions = random.sample(questions, num_questions)

        return questions
    
    @staticmethod
    def _normalize_role(role: str) -> str:
        """Map a free-text role/job-title string (e.g. 'Backend Engineer', 'Sr. React
        Developer') to the snake_case keys this hardcoded bank matches against — without
        this, the fallback bank (used whenever the AI is unavailable/quota-exhausted)
        silently returns zero questions for any role that isn't an exact snake_case match."""
        r = (role or "").lower()
        if any(k in r for k in ["frontend", "front-end", "front end", "react", "ui developer"]):
            return "frontend_developer"
        if any(k in r for k in ["devops", "cloud", "sre", "site reliability", "infrastructure"]):
            return "devops_engineer"
        if any(k in r for k in ["data scientist", "data science", "machine learning", "ml engineer", "ai engineer"]):
            return "machine_learning_engineer" if "machine learning" in r or "ml " in r else "data_scientist"
        if any(k in r for k in ["security", "cybersecurity", "infosec"]):
            return "cybersecurity_analyst"
        if any(k in r for k in ["full stack", "fullstack", "full-stack"]):
            return "fullstack_developer"
        if any(k in r for k in ["backend", "back-end", "back end"]):
            return "backend_developer"
        return "software_engineer"

    def _generate_role_specific_questions(self, role: str) -> List[InterviewQuestion]:
        """Generate questions specific to the target role"""
        questions = []
        role = self._normalize_role(role)

        # Role-specific technical questions
        if role == "software_engineer":
            questions.extend([
                InterviewQuestion(
                    'SE001',
                    'Explain your approach to debugging complex software issues.',
                    'technical', 'medium',
                    expected_keywords=['debug', 'logs', 'reproduce', 'hypothesis', 'testing'],
                    tips=['Describe your systematic approach', 'Mention specific tools']
                ),
                InterviewQuestion(
                    'SE002', 
                    'How do you ensure code quality and maintainability in your projects?',
                    'technical', 'medium',
                    expected_keywords=['testing', 'code review', 'standards', 'documentation'],
                    tips=['Mention testing strategies', 'Discuss collaboration practices']
                )
            ])
        elif role == "frontend_developer":
            questions.extend([
                InterviewQuestion(
                    'FD001',
                    'How do you optimize React application performance?',
                    'technical', 'medium',
                    expected_keywords=['react', 'memo', 'useMemo', 'useCallback', 'virtual dom', 'lazy-loading'],
                    sample_answer='To optimize React performance, you can use React.memo and useCallback to prevent unnecessary re-renders. Additionally, code-splitting with React.lazy can reduce bundle size, and useMemo helps with expensive calculations. Profiling with React DevTools is essential to identify bottlenecks.',
                    tips=['Discuss React-specific optimizations', 'Mention performance metrics']
                ),
                InterviewQuestion(
                    'FD002',
                    'Explain your approach to responsive design and cross-browser compatibility.',
                    'technical', 'medium',
                    expected_keywords=['responsive', 'css', 'media queries', 'browser support'],
                    tips=['Show understanding of different devices', 'Mention testing strategies']
                )
            ])
        elif role == "backend_developer":
            questions.extend([
                InterviewQuestion(
                    'BD001',
                    'How do you design and implement scalable REST APIs?',
                    'technical', 'medium',
                    expected_keywords=['rest', 'api', 'http', 'database', 'caching', 'scaling'],
                    tips=['Cover architecture decisions', 'Discuss performance considerations']
                ),
                InterviewQuestion(
                    'BD002',
                    'Describe your experience with database design and optimization.',
                    'technical', 'medium',
                    expected_keywords=['database', 'sql', 'normalization', 'indexing', 'query optimization'],
                    tips=['Discuss specific examples', 'Mention trade-offs']
                )
            ])
        elif role == "data_scientist":
            questions.extend([
                InterviewQuestion(
                    'DS001',
                    'How do you approach feature engineering for machine learning models?',
                    'technical', 'medium',
                    expected_keywords=['feature engineering', 'data preprocessing', 'ml', 'modeling'],
                    tips=['Discuss real examples', 'Mention validation strategies']
                ),
                InterviewQuestion(
                    'DS002',
                    'Explain how you would validate a machine learning model.',
                    'technical', 'medium',
                    expected_keywords=['validation', 'cross-validation', 'metrics', 'overfitting'],
                    tips=['Cover different validation approaches', 'Discuss metrics selection']
                )
            ])
        elif role == "devops_engineer":
            questions.extend([
                InterviewQuestion(
                    'DO001',
                    'How do you design and implement CI/CD pipelines?',
                    'technical', 'medium',
                    expected_keywords=['ci/cd', 'automation', 'testing', 'deployment', 'pipeline'],
                    tips=['Cover the entire pipeline', 'Discuss error handling']
                ),
                InterviewQuestion(
                    'DO002',
                    'Describe your approach to infrastructure monitoring and alerting.',
                    'technical', 'medium',
                    expected_keywords=['monitoring', 'alerting', 'metrics', 'logging', 'troubleshooting'],
                    tips=['Discuss specific tools', 'Mention incident response']
                )
            ])
        elif role == "fullstack_developer":
            questions.extend([
                InterviewQuestion(
                    'FS001',
                    'How do you manage state across frontend and backend in full-stack applications?',
                    'technical', 'medium',
                    expected_keywords=['state management', 'redux', 'context', 'database', 'api'],
                    tips=['Cover both client and server state', 'Discuss data flow']
                ),
                InterviewQuestion(
                    'FS002',
                    'Describe your process for full-stack application testing.',
                    'technical', 'medium',
                    expected_keywords=['testing', 'unit tests', 'integration tests', 'e2e testing'],
                    tips=['Cover different testing layers', 'Mention testing tools']
                )
            ])
        elif role == "machine_learning_engineer":
            questions.extend([
                InterviewQuestion(
                    'ML001',
                    'How do you deploy and monitor machine learning models in production?',
                    'technical', 'medium',
                    expected_keywords=['mlops', 'deployment', 'monitoring', 'model drift', 'serving'],
                    tips=['Discuss model lifecycle', 'Mention monitoring strategies']
                ),
                InterviewQuestion(
                    'ML002',
                    'Describe your approach to model optimization and hyperparameter tuning.',
                    'technical', 'medium',
                    expected_keywords=['optimization', 'hyperparameters', 'grid search', 'bayesian'],
                    tips=['Discuss trade-offs', 'Mention computational considerations']
                )
            ])
        elif role == "cybersecurity_analyst":
            questions.extend([
                InterviewQuestion(
                    'CY001',
                    'How do you approach vulnerability assessment and penetration testing?',
                    'technical', 'medium',
                    expected_keywords=['vulnerability', 'penetration testing', 'security assessment', 'threats'],
                    tips=['Cover methodology', 'Discuss reporting and remediation']
                ),
                InterviewQuestion(
                    'CY002',
                    'Describe your approach to incident response and forensics.',
                    'technical', 'medium',
                    expected_keywords=['incident response', 'forensics', 'log analysis', 'containment'],
                    tips=['Cover the incident lifecycle', 'Mention compliance requirements']
                )
            ])
        
        # Add role-specific behavioral questions
        behavioral_map = {
            "software_engineer": "How do you approach learning new technologies and staying current?",
            "frontend_developer": "How do you ensure your designs are accessible to all users?",
            "backend_developer": "How do you balance system performance with development speed?",
            "data_scientist": "How do you communicate complex data insights to non-technical stakeholders?",
            "devops_engineer": "How do you balance system reliability with deployment velocity?",
            "fullstack_developer": "How do you stay organized when working on both frontend and backend?",
            "machine_learning_engineer": "How do you ensure ethical considerations in your ML models?",
            "cybersecurity_analyst": "How do you stay ahead of emerging security threats?"
        }
        
        if role in behavioral_map:
            questions.append(InterviewQuestion(
                f'{role.upper()}_BH001',
                behavioral_map[role],
                'behavioral', 'medium',
                expected_keywords=['learning', 'communication', 'balance', 'organization'],
                tips=['Give specific examples', 'Show continuous learning mindset']
            ))
        
        return questions
    
    def _generate_job_specific_questions(self, job_requirements: Dict) -> List[InterviewQuestion]:
        """Generate questions specific to the job posting"""
        questions = []
        
        # Get job details
        title = job_requirements.get('title', '')
        company = job_requirements.get('company', '')
        location = job_requirements.get('location', '')
        skills = job_requirements.get('skills_required', [])
        description = job_requirements.get('description', '')
        
        # Create job-specific technical questions based on skills
        for skill in skills[:2]:  # Top 2 skills
            skill_name = skill.get('name', '')
            if skill_name:
                questions.append(InterviewQuestion(
                    f'JOB_SKILL_{skill_name[:3]}',
                    f"I see this role requires {skill_name}. Can you walk me through a specific project where you used {skill_name} to solve a challenging problem?",
                    'technical', 'medium',
                    expected_keywords=[skill_name.lower(), 'project', 'problem solving'],
                    tips=['Give a concrete example', 'Show depth of knowledge']
                ))
        
        # Add company-specific question if we have company info
        if company:
            questions.append(InterviewQuestion(
                'JOB_COMPANY',
                f"Why are you interested in working at {company}, and how does this role align with your career goals?",
                'behavioral', 'easy',
                expected_keywords=['company', 'career goals', 'motivation', 'alignment'],
                tips=['Show research about the company', 'Connect to your experience']
            ))
        
        # Add location-specific question if not remote
        if location and location.lower() != 'remote':
            questions.append(InterviewQuestion(
                'JOB_LOCATION',
                f"I see this role is located in {location}. How do you feel about the location, and what's your experience working in this area?",
                'behavioral', 'easy',
                expected_keywords=['location', 'relocation', 'experience'],
                tips=['Be honest about location preferences', 'Show flexibility']
            ))
        
        return questions


class InterviewPracticeSystem:
    """Main interview practice system"""
    
    def __init__(self):
        self.speech_analyzer = SpeechAnalyzer()
        self.keyword_analyzer = KeywordAnalyzer()
        self.question_generator = QuestionGenerator()
        self.llm = LLMClient()
        self.recognizer = sr.Recognizer() if SPEECH_RECOGNITION_AVAILABLE and sr else None
        
        # Feedback thresholds from config
        self.feedback_config = config['interview']['feedback']
    
    async def start_interview_session(self, job_requirements: Dict,
                                       role: str = "software_engineer",
                                       specific_job: bool = False,
                                       difficulty: str = "medium") -> Dict[str, Any]:
        """Start a new interview session with role-specific questions"""
        questions = await self.question_generator.generate_questions_for_job(
            self.llm,
            job_requirements,
            role=role,
            specific_job=specific_job,
            num_questions=5,
            difficulty=difficulty
        )

        session_data = {
            'session_id': f"int_{int(time.time())}",
            'role': role,
            'difficulty': difficulty,
            'questions': [{'id': q.question_id, 'text': q.question_text, 
                          'category': q.category, 'difficulty': q.difficulty,
                          'expected_keywords': q.expected_keywords,
                          'sample_answer': q.sample_answer}
                         for q in questions],
            'current_question_index': 0,
            'responses': [],
            'started_at': datetime.utcnow().isoformat(),
            'status': 'active',
            'job_context': job_requirements if specific_job else None
        }
        
        return session_data
    
    def listen_and_transcribe(self, timeout: int = 30) -> Optional[str]:
        """Listen to microphone and transcribe speech"""
        if not SPEECH_RECOGNITION_AVAILABLE or not sr:
            logger.error("Speech recognition not available. Please install: pip install SpeechRecognition")
            return None
            
        try:
            with sr.Microphone() as source:
                logger.info("Listening... Speak now.")
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = self.recognizer.listen(source, timeout=timeout)
                
                logger.info("Processing speech...")
                transcript = self.recognizer.recognize_google(audio)
                return transcript
                
        except sr.WaitTimeoutError:
            logger.warning("No speech detected within timeout")
            return None
        except sr.UnknownValueError:
            logger.warning("Could not understand speech")
            return None
        except Exception as e:
            logger.error(f"Speech recognition error: {e}")
            return None
    
    async def analyze_response(self, question: InterviewQuestion, 
                               response: str, audio_duration: float) -> InterviewFeedback:
        """Analyze user response and provide feedback using AI and heuristic analysis"""
        # 1. Speech Pattern Analysis (Local Heuristic)
        speech_analysis = self.speech_analyzer.analyze_speech(response, audio_duration)
        
        # 2. AI-Powered Technical Content Analysis
        ai_analysis = {}
        if self.llm.enabled:
            logger.info("Analyzing response using AI model...")
            ai_analysis = await self.llm.analyze_response(
                question.question_text, 
                response, 
                question.expected_keywords
            )
        
        # 3. Keyword Matching (Fallback/Complementary)
        keyword_analysis = self.keyword_analyzer.analyze_keywords(
            response, question.category, expected_keywords=question.expected_keywords
        )
        
        # Check for negative/empty responses
        negative_responses = ["don't know", "dont know", "no idea", "not sure", "don't recall", "forgot"]
        is_negative = any(nr in response.lower() for nr in negative_responses) or len(response.split()) < 3
        
        # Calculate Scores
        filler_threshold = self.feedback_config['min_filler_words_threshold']
        filler_score = max(0, 100 - (speech_analysis['filler_percentage'] / filler_threshold * 100))
        pacing_score = self.speech_analyzer.evaluate_pacing(speech_analysis)
        
        # Prioritize AI score if available
        if ai_analysis:
            technical_score = ai_analysis.get('technical_accuracy', 0)
            keyword_score = ai_analysis.get('depth_score', keyword_analysis['keyword_score'])
        else:
            keyword_score = keyword_analysis['keyword_score']
            if is_negative:
                technical_score = 0
            else:
                technical_score = (keyword_score * 0.8) + (pacing_score * 0.2)

        communication_score = (filler_score + pacing_score) / 2
        
        if is_negative:
            overall_score = communication_score * 0.2
        else:
            overall_score = (technical_score * 0.6 + communication_score * 0.4)
        
        # Generate final lists of strengths and improvements
        strengths = []
        improvements = []
        
        if ai_analysis:
            strengths.extend(ai_analysis.get('strengths', []))
            improvements.extend(ai_analysis.get('improvements', []))
            if ai_analysis.get('depth_feedback'):
                strengths.append(ai_analysis['depth_feedback'])
        
        # Add speech-based feedback
        if not is_negative:
            if speech_analysis['filler_percentage'] < 5:
                strengths.append("Clean speech with minimal filler words")
            
            if 120 <= speech_analysis['speaking_rate_wpm'] <= 160:
                strengths.append("Perfect professional speaking pace")
            elif speech_analysis['speaking_rate_wpm'] > 160:
                improvements.append("Try to speak a bit slower for clarity")
            else:
                improvements.append("Try to speak a bit faster to maintain active engagement")
        else:
            improvements.append("Candidate indicated limited knowledge on this specific topic.")

        return InterviewFeedback(
            overall_score=round(overall_score, 2),
            technical_accuracy=round(technical_score, 2),
            communication_score=round(communication_score, 2),
            filler_words_used=speech_analysis['filler_words_used'],
            filler_word_count=speech_analysis['filler_word_count'],
            speaking_rate_wpm=speech_analysis['speaking_rate_wpm'],
            pacing_score=round(pacing_score, 2),
            strengths=strengths,
            improvements=improvements,
            keywords_matched=keyword_analysis['matched_keywords'],
            keywords_missing=keyword_analysis['missing_keywords'],
            suggested_answers=[question.sample_answer] if question.sample_answer else []
        )
    
    async def end_session(self, session_data: Dict) -> Dict[str, Any]:
        """End interview session and generate summary"""
        responses = session_data.get('responses', [])
        
        if not responses:
            return {'error': 'No responses recorded'}
        
        total_score = sum(r['feedback']['overall_score'] for r in responses) / len(responses)
        
        summary = {
            'session_id': session_data['session_id'],
            'total_questions': len(responses),
            'average_score': round(total_score, 2),
            'total_duration_minutes': session_data.get('duration_minutes', 0),
            'completed_at': datetime.utcnow().isoformat(),
            'feedback': {
                'overall_performance': 'Excellent' if total_score >= 80 else 
                                       'Good' if total_score >= 60 else 
                                       'Needs Improvement',
                'strengths': [],
                'areas_for_improvement': []
            }
        }
        
        # Aggregate strengths and improvements
        all_strengths = []
        all_improvements = []
        for r in responses:
            all_strengths.extend(r['feedback'].get('strengths', []))
            all_improvements.extend(r['feedback'].get('improvements', []))
        
        summary['feedback']['strengths'] = list(set(all_strengths))[:5]
        summary['feedback']['areas_for_improvement'] = list(set(all_improvements))[:5]
        
        return summary


# Example usage
if __name__ == "__main__":
    async def test_interview():
        system = InterviewPracticeSystem()
        
        # Sample job requirements
        job_requirements = {
            'title': 'Senior Software Engineer',
            'skills_required': [
                {'name': 'Python', 'category': 'programming'},
                {'name': 'React', 'category': 'framework'},
                {'name': 'PostgreSQL', 'category': 'database'}
            ],
            'experience_level': 'senior'
        }
        
        # Start session
        session = await system.start_interview_session(job_requirements, 'mixed')
        print(f"Interview Session Started: {session['session_id']}")
        print(f"Questions: {len(session['questions'])}")
        
        # Simulate user response (in real usage, would use listen_and_transcribe)
        sample_response = "I have extensive experience with Python, working on various web applications and data processing systems. I particularly enjoy using React for building interactive user interfaces."
        audio_duration = 15.0  # seconds
        
        # Analyze response
        question = InterviewQuestion(
            'T-TEST', 'Tell me about your Python experience',
            'technical', 'medium'
        )
        
        feedback = await system.analyze_response(question, sample_response, audio_duration)
        
        print(f"\nInterview Feedback:")
        print(f"Overall Score: {feedback.overall_score}/100")
        print(f"Technical Accuracy: {feedback.technical_accuracy}/100")
        print(f"Communication: {feedback.communication_score}/100")
        print(f"Speaking Rate: {feedback.speaking_rate_wpm} WPM")
        print(f"Filler Words: {feedback.filler_word_count}")
        print(f"\nStrengths: {', '.join(feedback.strengths)}")
        print(f"Improvements: {', '.join(feedback.improvements)}")
        print(f"\nKeywords Matched: {feedback.keywords_matched}")
        print(f"Keywords Missing: {feedback.keywords_missing}")
    
    asyncio.run(test_interview())
