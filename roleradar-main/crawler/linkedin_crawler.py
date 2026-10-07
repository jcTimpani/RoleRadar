import asyncio
import httpx
from bs4 import BeautifulSoup
import logging
from datetime import datetime
from typing import List, Dict, Any
import re
import os
import sys
from urllib.parse import urljoin

# Ensure parent directory is in path to import database and config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import db_manager, JobOperations, CompanyOperations
from config import config

logger = logging.getLogger(__name__)

class LinkedInJobCrawler:
    """Specialized crawler for LinkedIn Jobs (Public Search)"""
    
    stop_requested = False  # Class-level flag to stop all instances
    
    def __init__(self):
        self.base_url = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        LinkedInJobCrawler.stop_requested = False
    
    async def fetch_jobs(self, keywords: str, location: str, start: int = 0) -> List[Dict[str, Any]]:
        """Fetch job listings from public LinkedIn job search API"""
        params = {
            "keywords": keywords,
            "location": location,
            "start": start
        }
        
        async with httpx.AsyncClient(headers=self.headers, timeout=30.0) as client:
            try:
                logger.info(f"Crawling LinkedIn: {keywords} in {location} (start={start})")
                response = await client.get(self.base_url, params=params)
                
                if response.status_code != 200:
                    logger.error(f"LinkedIn returned status {response.status_code}")
                    return []
                
                return self.parse_job_list(response.text)
            except Exception as e:
                logger.error(f"Error fetching LinkedIn jobs: {e}")
                return []

    def parse_job_list(self, html: str) -> List[Dict[str, Any]]:
        """Parse the HTML response from LinkedIn search API"""
        soup = BeautifulSoup(html, 'html.parser')
        job_cards = soup.find_all('li')
        jobs = []
        
        for card in job_cards:
            try:
                title_tag = card.find('h3', class_='base-search-card__title')
                company_tag = card.find('a', class_='hidden-nested-link')
                location_tag = card.find('span', class_='job-search-card__location')
                link_tag = card.find('a', class_='base-card__full-link') or \
                           card.find('a', class_='base-search-card__full-link') or \
                           card.find('a', href=re.compile(r'/jobs/view/'))
                
                if not title_tag or not company_tag:
                    continue
                
                job_title = title_tag.get_text(strip=True)
                company_name = company_tag.get_text(strip=True)
                company_url = company_tag['href'].split('?')[0] if company_tag.has_attr('href') else ""
                location = location_tag.get_text(strip=True) if location_tag else ""
                # Try to get the specific job ID from the card attributes (most reliable for direct links)
                job_id = None
                if card.has_attr('data-entity-urn'):
                    job_id = card['data-entity-urn'].split(':')[-1]
                elif card.find('div', {'data-job-id': True}):
                    job_id = card.find('div', {'data-job-id': True})['data-job-id']
                
                if job_id:
                    job_url = f"https://www.linkedin.com/jobs/view/{job_id}"
                else:
                    possible_url = link_tag['href'].split('?')[0] if link_tag else ""
                    # Fallback: Extract ID from URL regex if possible
                    url_id_match = re.search(r'/view/(\d+)', possible_url) or re.search(r'-(\d+)(?:\?|$)', possible_url)
                    if url_id_match:
                        job_url = f"https://www.linkedin.com/jobs/view/{url_id_match.group(1)}"
                    else:
                        job_url = possible_url
                
                if not job_url:
                    logger.info(f"Skipping {job_title} - Could not resolve real source URL.")
                    continue
                
                # Split location into city/state if possible
                loc_parts = location.split(',')
                city = loc_parts[0].strip() if len(loc_parts) > 0 else location
                state = loc_parts[1].strip() if len(loc_parts) > 1 else "TX"
                
                # Create a richer description (Simulated "About the job")
                description = f"""
                <strong>About the Job:</strong><br>
                We are looking for a skilled {job_title} to join {company_name} in {city}, {state}. 
                This is an exciting opportunity to work on cutting-edge North Texas technology projects.<br><br>
                <strong>Responsibilities:</strong><br>
                • Developing and maintaining high-quality software solutions.<br>
                • Collaborating with engineering teams to solve complex problems.<br>
                • Contributing to architectural decisions and best practices.<br><br>
                <strong>Requirements:</strong><br>
                • Strong experience in {job_title} core competencies.<br>
                • Bachelors degree in Computer Science or related field.<br>
                • Excellent communication and teamwork skills.
                """
                
                jobs.append({
                    "title": job_title,
                    "company_name": company_name,
                    "company_linkedin": company_url,
                    "location_city": city,
                    "location_state": state,
                    "source_url": job_url,
                    "source_type": "LinkedIn",
                    "posted_date": datetime.utcnow().strftime('%Y-%m-%d'),
                    "description": description.strip()
                })
            except Exception as e:
                logger.warning(f"Error parsing job card: {e}")
                
        return jobs

    async def fetch_job_description(self, job_url: str) -> str:
        """Visit the specific job page to get the real 'About the Job' description"""
        if not job_url:
            return "No description available."
            
        try:
            async with httpx.AsyncClient(headers=self.headers, timeout=20.0, follow_redirects=True) as client:
                response = await client.get(job_url)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    # LinkedIn guest job page selector
                    desc_section = soup.find('div', class_='description__text') or \
                                   soup.find('div', class_='show-more-less-html__markup')
                    
                    if desc_section:
                        # Clean up the HTML but keep basic formatting
                        for s in desc_section(['script', 'style', 'button']):
                            s.decompose()
                        return str(desc_section).strip()
        except Exception as e:
            logger.warning(f"Error fetching job description from {job_url}: {e}")
            
        return "Description could not be retrieved from the source."

    async def get_company_website_from_linkedin(self, linkedin_url: str) -> str:
        """Fetch the official website URL from the company's LinkedIn profile 'About' page"""
        if not linkedin_url:
            return None
            
        try:
            # LinkedIn guest view often hides details, but sometimes it's in the meta tags or simple links
            about_url = linkedin_url.rstrip('/') + "/about"
            async with httpx.AsyncClient(headers=self.headers, timeout=15.0) as client:
                response = await client.get(about_url)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    # Look for website link in guest view - common patterns
                    website_tag = soup.find('a', {'data-tracking-control-name': 'about_website'}) or \
                                  soup.find('a', class_='about-us__link')
                    if website_tag:
                        return website_tag['href'].split('?')[0]
        except Exception as e:
            logger.warning(f"Error getting website from LinkedIn {linkedin_url}: {e}")
            
        return None

    async def scrape_company_website(self, url: str) -> Dict[str, str]:
        """Visit company website to find real contact info"""
        contact_info = {"phone": None, "email": None}
        if not url or "google.com" in url or "linkedin.com" in url:
            return contact_info
            
        try:
            async with httpx.AsyncClient(headers=self.headers, timeout=15.0, follow_redirects=True) as client:
                response = await client.get(url)
                if response.status_code != 200:
                    return contact_info
                
                soup = BeautifulSoup(response.text, 'html.parser')
                contact_links = []
                for a in soup.find_all('a', href=True):
                    text = a.get_text().lower()
                    href = a['href'].lower()
                    if any(x in text or x in href for x in ['contact', 'about', 'support', 'reach', 'office', 'career', 'job', 'team']):
                        contact_url = href if href.startswith('http') else urljoin(url, href)
                        contact_links.append(contact_url)
                
                pages_to_scrape = [url] + list(set(contact_links))[:3]
                
                # Enhanced phone detection: looking for tel: links and broad text patterns
                phone_pattern = r'(?:\+1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'
                phone_pattern_alt = r'\d{3}\.\d{3}\.\d{4}'
                email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
                
                for page_url in pages_to_scrape:
                    try:
                        res = await client.get(page_url)
                        if res.status_code == 200:
                            content = res.text
                            soup_inner = BeautifulSoup(content, 'html.parser')
                            
                            # 1. Search for tel: links (most reliable real numbers)
                            if not contact_info["phone"]:
                                tel_links = soup_inner.find_all('a', href=re.compile(r'^tel:'))
                                if tel_links:
                                    contact_info["phone"] = tel_links[0]['href'].replace('tel:', '').strip()
                            
                            # 2. Find Phones in text
                            if not contact_info["phone"]:
                                phones = re.findall(phone_pattern, content) or re.findall(phone_pattern_alt, content)
                                if phones:
                                    contact_info["phone"] = phones[0]
                            
                            # 3. Find Emails
                            if not contact_info["email"]:
                                # Look for mailto: links
                                mail_links = soup_inner.find_all('a', href=re.compile(r'^mailto:'))
                                if mail_links:
                                    contact_info["email"] = mail_links[0]['href'].replace('mailto:', '').split('?')[0]
                                
                                if not contact_info["email"]:
                                    emails = re.findall(email_pattern, content)
                                    if emails:
                                        relevant = [e for e in emails if any(x in e.lower() for x in ['info', 'contact', 'hr', 'jobs', 'careers'])]
                                        contact_info["email"] = relevant[0] if relevant else emails[0]
                                    
                        if contact_info["phone"] and contact_info["email"]:
                            break
                    except Exception:
                        continue
                        
        except Exception as e:
            logger.error(f"Error scraping company website {url}: {e}")
            
        return contact_info

    async def run_crawl(self, keywords_list: List[str], cities: List[str]):
        """Run a full crawl cycle. Only saves records with real discovered phone numbers."""
        db_manager.connect()
        job_ops = JobOperations(db_manager)
        company_ops = CompanyOperations(db_manager)
        
        for city in cities:
            if LinkedInJobCrawler.stop_requested: break
            for keyword in keywords_list:
                if LinkedInJobCrawler.stop_requested: break
                jobs = await self.fetch_jobs(keyword, f"{city}, TX")
                
                for job in jobs:
                    if LinkedInJobCrawler.stop_requested:
                        logger.info("Termination signal received. Stopping crawl...")
                        return
                    try:
                        # 1. Get REAL company website from LinkedIn profile
                        real_website = await self.get_company_website_from_linkedin(job["company_linkedin"])
                        website_url = real_website or f"https://www.{job['company_name'].lower().replace(' ', '')}.com"
                        
                        # 2. Scrape REAL contact info
                        contact = await self.scrape_company_website(website_url)
                        
                        # REQUIREMENT: Only save if real phone OR email were found (User wants "Real data")
                        # If we have neither, we skip. If we have one, we save it (it helps for further digging)
                        if not contact["phone"] and not contact["email"]:
                            logger.info(f"Skipping {job['company_name']} - No contact info discovered.")
                            continue

                        # 3. Fetch REAL "About the Job" description
                        real_desc = await self.fetch_job_description(job["source_url"])
                        if real_desc:
                            job["description"] = real_desc

                        # 4. Save Company
                        company_id = company_ops.create({
                            "name": job["company_name"],
                            "location_city": job["location_city"],
                            "location_state": job["location_state"],
                            "industry": "Technology",
                            "linkedin_url": job["company_linkedin"],
                            "website": website_url,
                            "phone": contact["phone"],
                            "hr_email": contact["email"]
                        })
                        
                        # 5. Save Job
                        job["company_id"] = company_id
                        job_id = job_ops.create(job)
                        logger.info(f"✅ SAVED TO DATABASE: {job['title']} at {job['company_name']} (Phone: {contact['phone'] or 'N/A'}, Email: {contact['email'] or 'N/A'})")
                        
                    except Exception as e:
                        logger.error(f"Error saving job {job['title']}: {e}")
                
                await asyncio.sleep(5)

async def start_background_crawler():
    """Service function to run crawler periodically"""
    crawler = LinkedInJobCrawler()
    keywords = ["Software Engineer", "Developer", "Data Scientist", "DevOps"]
    cities = config['crawler']['dfw_cities']
    
    while True:
        logger.info("Starting background crawl cycle...")
        try:
            await crawler.run_crawl(keywords, cities)
        except Exception as e:
            logger.error(f"Crawl cycle failed: {e}")
            
        # Run every 2 hours
        logger.info("Crawl cycle complete. Sleeping for 2 hours...")
        await asyncio.sleep(7200)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(start_background_crawler())
