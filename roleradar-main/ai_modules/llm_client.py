import os
import json
import logging
import asyncio
import httpx
from typing import Dict, List, Any, Optional
from config import config
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class LLMClient:
    """AI Client for generating and analyzing interview content using Google Gemini"""
    
    def __init__(self):
        # Load API key from environment or config
        self.api_key = os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            conf_key = config.get('api_keys', {}).get('gemini')
            if conf_key and "${" not in conf_key:
                self.api_key = conf_key
        
        self.enabled = bool(self.api_key)
        self.model = "gemini-flash-latest"
        self.api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        
        if not self.enabled:
            logger.warning("LLMClient: No Google Gemini API key found. Set GEMINI_API_KEY in .env")
        else:
            logger.info(f"LLMClient: Gemini initialized using {self.model}")

    async def _call_gemini(self, prompt: str, system_instruction: str = None, 
                             file_data: bytes = None, mime_type: str = None) -> str:
        """Call Gemini API via HTTP with optional binary data"""
        if not self.api_key:
            return ""

        # Base payload
        parts = []
        if system_instruction:
            # For older versions/models, prepend instruction to prompt
            parts.append({"text": f"INSTRUCTIONS: {system_instruction}\n\n"})
        
        parts.append({"text": prompt})

        if file_data and mime_type:
            import base64
            encoded_data = base64.b64encode(file_data).decode('utf-8')
            parts.append({
                "inline_data": {
                    "mime_type": mime_type,
                    "data": encoded_data
                }
            })

        # "gemini-flash-latest" only resolves on v1beta (v1 stable 404s on this alias
        # unconditionally, so retrying there wastes a call). Retry v1beta itself on the
        # model's transient 503 "high demand" responses instead — those clear quickly.
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"

        payload = {"contents": [{"parts": parts}]}
        if system_instruction:
            payload["system_instruction"] = {"parts": [{"text": system_instruction}]}
            payload["contents"][0]["parts"] = [p for p in parts if "INSTRUCTIONS:" not in p.get("text", "")]
        payload["generationConfig"] = {"responseMimeType": "application/json"}

        max_attempts = 3
        async with httpx.AsyncClient(timeout=60.0) as client:
            for attempt in range(1, max_attempts + 1):
                try:
                    response = await client.post(url, json=payload)
                    if response.status_code == 200:
                        data = response.json()
                        if "candidates" in data and len(data["candidates"]) > 0:
                            content = data["candidates"][0]["content"]["parts"][0]["text"]
                            # Clean up potential markdown code blocks
                            if "```json" in content:
                                content = content.split("```json")[1].split("```")[0]
                            elif "```" in content:
                                content = content.split("```")[1].split("```")[0]
                            return content.strip()
                    elif response.status_code == 503 and attempt < max_attempts:
                        logger.warning(f"Gemini v1beta busy (attempt {attempt}/{max_attempts}), retrying...")
                        await asyncio.sleep(2 * attempt)
                        continue
                    else:
                        logger.warning(f"Gemini v1beta failed: {response.status_code} - {response.text}")
                        break
                except Exception as e:
                    logger.error(f"Gemini v1beta Exception: {e}")
                    break

        return ""

    async def generate_questions(self, role: str, job_context: Dict = None, num_questions: int = 5, difficulty: str = "medium") -> List[Dict]:
        """Generate tailored interview questions in real-time using Gemini"""
        if not self.enabled:
            return []

        context_str = f"Role: {role}"
        if job_context:
            context_str += f"\nJob Details: {json.dumps(job_context)}"

        system_instruction = "You are a senior technical recruiter who returns strictly structured JSON."
        prompt = f"""
        Generate {num_questions} realistic interview questions, all at {difficulty.upper()} difficulty, for:
        {context_str}

        Every question's "difficulty" field must be exactly "{difficulty}" — calibrate the question's
        depth and complexity to that level (easy = fundamentals/definitions, medium = applied
        scenarios, hard = deep system design / edge cases / trade-off analysis).

        Return exactly this JSON structure:
        {{
          "questions": [
            {{
              "id": "AI_001",
              "question_text": "text",
              "category": "technical/behavioral",
              "difficulty": "{difficulty}",
              "expected_keywords": ["keyword1", "keyword2"],
              "sample_answer": "answer",
              "tips": ["tip1", "tip2"]
            }}
          ]
        }}
        """
        
        content = await self._call_gemini(prompt, system_instruction)
        if not content:
            return []
            
        try:
            data = json.loads(content)
            return data.get('questions', [])
        except Exception as e:
            logger.error(f"Failed to parse Gemini JSON: {e}")
            return []

    async def analyze_response(self, question: str, answer: str, context: List[str] = None) -> Dict:
        """Analyze a candidate's response in real-time using Gemini knowledge"""
        if not self.enabled:
            return {}

        system_instruction = "You are a highly critical technical interviewer. Return JSON."
        prompt = f"""
        Evaluate this answer:
        Question: {question}
        User Answer: {answer}
        Reference Keywords: {context}

        Rules:
        1. If answer is "I don't know" or irrelevant, technical_accuracy = 0.
        2. technical_accuracy is out of 100.
        3. depth_score is 0-100 indicating how comprehensive the answer is.

        Return exactly this JSON structure:
        {{
          "technical_accuracy": 85.0,
          "depth_score": 70.0,
          "strengths": ["strength1"],
          "improvements": ["improvement1"],
          "feedback_summary": "summary"
        }}
        """

        content = await self._call_gemini(prompt, system_instruction)
        if not content:
            return {}
            
        try:
            return json.loads(content)
        except Exception as e:
            logger.error(f"Failed to parse Gemini analysis: {e}")
            return {}
    async def analyze_skill_gap(self, resume_text: str, job_description: str) -> Dict:
        """Analyze gaps between resume and job description using AI"""
        if not self.enabled:
            return {}

        system_instruction = "You are an expert career coach and technical recruiter. Return JSON."
        prompt = f"""
        Compare this resume against the job description and identify skill gaps.
        
        RESUME:
        {resume_text[:4000]}
        
        JOB DESCRIPTION:
        {job_description[:4000]}

        Return exactly this JSON structure:
        {{
          "match_percentage": 75.0,
          "matched_skills": ["Skill A", "Skill B"],
          "missing_skills": ["Skill C", "Skill D"],
          "recommendations": [
            {{
              "skill": "Skill C",
              "reason": "Required for X in job description",
              "resources": ["Course link or name", "Tutorial name"]
            }}
          ],
          "overall_summary": "1-2 sentences on how well they match."
        }}
        """

        content = await self._call_gemini(prompt, system_instruction)
        if not content:
            return {}
            
        try:
            return json.loads(content)
        except Exception as e:
            logger.error(f"Failed to parse Skill Gap JSON: {e}")
            return {}

    async def analyze_skill_gap_file(self, file_content: bytes, mime_type: str, job_description: str) -> Dict:
        """Analyze gaps using direct file upload to Gemini (handles images/scans)"""
        if not self.enabled:
            return {}

        system_instruction = "You are an expert career coach. Analyze the attached resume file against the job description. Return JSON."
        prompt = f"""
        Extract skills from the attached resume file and compare it against this job description.
        If the file is a scan, use your OCR capabilities to read it.
        
        JOB DESCRIPTION:
        {job_description[:4000]}

        Return exactly this JSON structure:
        {{
          "match_percentage": 75.0,
          "matched_skills": ["Skill A", "Skill B"],
          "missing_skills": ["Skill C", "Skill D"],
          "recommendations": [
            {{
              "skill": "Skill C",
              "reason": "Required for X in job description",
              "resources": ["Course link or name", "Tutorial name"]
            }}
          ],
          "overall_summary": "1-2 sentences on how well they match."
        }}
        """

        content = await self._call_gemini(prompt, system_instruction, file_data=file_content, mime_type=mime_type)
        if not content:
            return {}
            
        try:
            return json.loads(content)
        except Exception as e:
            logger.error(f"Failed to parse Skill Gap File JSON: {e}")
            return {}
