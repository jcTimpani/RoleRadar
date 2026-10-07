import os
import logging
import httpx
from typing import Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class JSearchClient:
    """Client for JSearch (via RapidAPI), which reads Google for Jobs — a legitimate,
    permitted downstream API over job postings Indeed/LinkedIn/Glassdoor/ZipRecruiter
    voluntarily publish for Google's indexing. Used instead of scraping those sites
    directly, since their own robots.txt/ToS prohibit or restrict that."""

    BASE_URL = "https://jsearch.p.rapidapi.com/search-v2"
    HOST = "jsearch.p.rapidapi.com"

    US_STATE_ABBR = {
        "texas": "TX", "california": "CA", "new york": "NY", "florida": "FL",
        "illinois": "IL", "pennsylvania": "PA", "arizona": "AZ", "north carolina": "NC",
    }

    def __init__(self):
        self.api_key = os.environ.get("RAPIDAPI_KEY")
        self.enabled = bool(self.api_key)
        if not self.enabled:
            logger.warning("JSearchClient: No RAPIDAPI_KEY found. Set RAPIDAPI_KEY in .env")

    async def search(self, query: str, location: str, num_pages: int = 1) -> List[Dict]:
        """Search for real job listings. `query` is typically 'role keywords',
        `location` a city/region string (e.g. 'Dallas, TX'). Returns a list of
        raw JSearch job result dicts, or [] on any failure/empty result."""
        if not self.enabled:
            return []

        headers = {
            "X-RapidAPI-Key": self.api_key,
            "X-RapidAPI-Host": self.HOST,
        }
        params = {
            "query": f"{query} in {location}",
            "page": "1",
            "num_pages": str(num_pages),
            "date_posted": "month",
        }

        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                response = await client.get(self.BASE_URL, headers=headers, params=params)
                if response.status_code != 200:
                    logger.warning(f"JSearch request failed: {response.status_code} - {response.text[:300]}")
                    return []
                data = response.json()
                return (data.get("data") or {}).get("jobs", []) or []
        except Exception as e:
            logger.error(f"JSearch request exception: {type(e).__name__}: {e}")
            return []

    @staticmethod
    def to_job_record(result: Dict) -> Optional[Dict]:
        """Map a raw JSearch result into the shape JobOperations.create()/CompanyOperations.create() expect."""
        title = result.get("job_title")
        employer = result.get("employer_name")
        apply_link = result.get("job_apply_link")
        if not title or not employer or not apply_link:
            return None

        state_raw = (result.get("job_state") or "").strip().lower()
        state_abbr = JSearchClient.US_STATE_ABBR.get(state_raw, result.get("job_state") or "TX")
        if len(state_abbr) > 2:
            state_abbr = "TX"  # unmapped full state name — DFW-focused search, safe fallback

        return {
            "company_name": employer,
            "company_website": result.get("employer_website"),
            "company_logo": result.get("employer_logo"),
            "title": title,
            "description": result.get("job_description") or "",
            "location_city": result.get("job_city"),
            "location_state": state_abbr,
            "job_type": result.get("job_employment_type") or "Full-time",
            "remote_policy": "remote" if result.get("job_is_remote") else "onsite",
            "salary_min": result.get("job_min_salary"),
            "salary_max": result.get("job_max_salary"),
            "source_url": apply_link,
            "source_type": (result.get("job_publisher") or "JSearch").strip(),
            "posted_date": (result.get("job_posted_at_datetime_utc") or "")[:10] or None,
        }
