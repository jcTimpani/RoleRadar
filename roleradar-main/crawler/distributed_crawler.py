"""
Distributed Web Crawler Architecture
Uses message queues (Redis) and worker pools with respectful rate limiting
"""

import asyncio
import aiohttp
import redis
import json
import logging
import time
import hashlib
from datetime import datetime
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
import httpx
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import requests

from config import config

# Setup logging
logging.basicConfig(
    level=getattr(logging, config['app'].get('log_level', 'INFO')),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class CrawlResult:
    """Result of a web crawling operation"""
    url: str
    success: bool
    content: Optional[str] = None
    status_code: Optional[int] = None
    error_message: Optional[str] = None
    crawl_time_ms: int = 0
    links_found: List[str] = field(default_factory=list)
    data_extracted: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class CrawlTask:
    """A task to be processed by the crawler"""
    url: str
    task_id: str
    priority: int = 0  # 0 = normal, higher = more important
    max_depth: int = 3
    current_depth: int = 0
    company_id: Optional[int] = None
    source: str = 'general'
    metadata: Dict[str, Any] = field(default_factory=dict)


class RateLimiter:
    """Respectful rate limiting with token bucket algorithm"""
    
    def __init__(self, requests_per_second: float = 0.5):
        self.min_interval = 1.0 / requests_per_second
        self.last_request_time = 0
        self.lock = asyncio.Lock()
    
    async def acquire(self):
        async with self.lock:
            current_time = time.time()
            time_since_last = current_time - self.last_request_time
            if time_since_last < self.min_interval:
                await asyncio.sleep(self.min_interval - time_since_last)
            self.last_request_time = time.time()


class RobotsTxtChecker:
    """Check robots.txt compliance"""
    
    def __init__(self):
        self._cache = {}
    
    async def can_fetch(self, url: str, user_agent: str = '*') -> bool:
        """Check if URL can be fetched according to robots.txt"""
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        
        if robots_url in self._cache:
            robots_content = self._cache[robots_url]
        else:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(robots_url, follow_redirects=True)
                    if response.status_code == 200:
                        robots_content = response.text
                    else:
                        robots_content = None
                self._cache[robots_url] = robots_content
            except Exception as e:
                logger.warning(f"Failed to fetch robots.txt: {e}")
                robots_content = None
        
        if not robots_content:
            return True  # Default allow if no robots.txt
        
        # Simple robots.txt parser
        can_fetch = True
        current_section = 'user-agent'
        applicable = False
        
        for line in robots_content.split('\n'):
            line = line.strip().lower()
            if not line or line.startswith('#'):
                continue
            
            if line.startswith('user-agent:'):
                if applicable:
                    break  # End of current section
                agent = line.split(':')[1].strip()
                if agent == '*' or agent == user_agent.lower():
                    applicable = True
                else:
                    applicable = False
            
            elif line.startswith('disallow:'):
                path = line.split(':')[1].strip()
                if applicable and path:
                    if url.startswith(f"{parsed.scheme}://{parsed.netloc}{path}"):
                        can_fetch = False
                        break
        
        return can_fetch


class BaseCrawler(ABC):
    """Abstract base class for web crawlers"""
    
    def __init__(self, name: str, rate_limiter: RateLimiter):
        self.name = name
        self.rate_limiter = rate_limiter
        self.robots_checker = RobotsTxtChecker()
        self.session = None
        self._setup_session()
    
    def _setup_session(self):
        """Setup HTTP session with proper headers"""
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': config['crawler']['user_agent'],
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        })
    
    async def _fetch_page(self, url: str) -> CrawlResult:
        """Fetch a single page with rate limiting"""
        start_time = time.time()
        
        # Check robots.txt
        if config['crawler']['respect_robots_txt']:
            if not await self.robots_checker.can_fetch(url):
                logger.info(f"Blocked by robots.txt: {url}")
                return CrawlResult(
                    url=url,
                    success=False,
                    error_message="Blocked by robots.txt",
                    crawl_time_ms=int((time.time() - start_time) * 1000)
                )
        
        # Apply rate limiting
        await self.rate_limiter.acquire()
        
        try:
            async with httpx.AsyncClient(
                timeout=config['crawler']['timeout'],
                follow_redirects=True
            ) as client:
                response = await client.get(
                    url,
                    headers={'User-Agent': config['crawler']['user_agent']}
                )
                
                crawl_time = int((time.time() - start_time) * 1000)
                
                if response.status_code == 200:
                    # Parse links
                    soup = BeautifulSoup(response.text, 'lxml')
                    links = [a.get('href') for a in soup.find_all('a', href=True)]
                    
                    return CrawlResult(
                        url=url,
                        success=True,
                        content=response.text,
                        status_code=200,
                        crawl_time_ms=crawl_time,
                        links_found=links
                    )
                else:
                    return CrawlResult(
                        url=url,
                        success=False,
                        status_code=response.status_code,
                        error_message=f"HTTP {response.status_code}",
                        crawl_time_ms=crawl_time
                    )
                    
        except Exception as e:
            return CrawlResult(
                url=url,
                success=False,
                error_message=str(e),
                crawl_time_ms=int((time.time() - start_time) * 1000)
            )
    
    @abstractmethod
    async def crawl(self, url: str, **kwargs) -> CrawlResult:
        """Crawl a specific URL - to be implemented by subclasses"""
        pass
    
    @abstractmethod
    def extract_data(self, content: str, url: str) -> Dict[str, Any]:
        """Extract structured data from page content"""
        pass


class CompanyCrawler(BaseCrawler):
    """Crawler for company information"""
    
    def __init__(self):
        super().__init__("company_crawler", RateLimiter(0.5))
    
    async def crawl(self, url: str, **kwargs) -> CrawlResult:
        result = await self._fetch_page(url)
        if result.success:
            result.data_extracted = self.extract_data(result.content, url)
        return result
    
    def extract_data(self, content: str, url: str) -> Dict[str, Any]:
        """Extract company information from page"""
        soup = BeautifulSoup(content, 'lxml')
        data = {
            'url': url,
            'company_name': None,
            'industry': None,
            'size': None,
            'location': None,
            'phone': None,
            'hr_email': None,
            'description': None
        }
        
        # Basic extraction - can be enhanced with NLP
        # This is a simplified version
        try:
            # Company name from title
            title = soup.find('title')
            if title:
                data['company_name'] = title.text.strip().split('|')[0].strip()
            
            # Extract phone numbers
            import re
            phone_pattern = r'\+?1?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'
            phones = re.findall(phone_pattern, content)
            if phones:
                data['phone'] = phones[0]
            
            # Extract emails
            email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
            emails = re.findall(email_pattern, content)
            if emails:
                # Filter out no-reply, noreply, etc.
                hr_emails = [e for e in emails if 'noreply' not in e.lower()]
                if hr_emails:
                    data['hr_email'] = hr_emails[0]
            
        except Exception as e:
            logger.error(f"Error extracting company data: {e}")
        
        return data


class JobBoardCrawler(BaseCrawler):
    """Crawler for job postings"""
    
    def __init__(self, job_board_name: str):
        super().__init__(f"jobboard_{job_board_name}", RateLimiter(0.3))
        self.job_board_name = job_board_name
    
    async def crawl(self, url: str, **kwargs) -> CrawlResult:
        result = await self._fetch_page(url)
        if result.success:
            result.data_extracted = self.extract_data(result.content, url)
        return result
    
    def extract_data(self, content: str, url: str) -> Dict[str, Any]:
        """Extract job posting information"""
        soup = BeautifulSoup(content, 'lxml')
        data = {
            'url': url,
            'source': self.job_board_name,
            'job_title': None,
            'company_name': None,
            'location': None,
            'salary': None,
            'description': None,
            'requirements': [],
            'skills_required': [],
            'posted_date': None,
            'application_url': None
        }
        
        try:
            # Basic extraction - job boards have different structures
            # This would need customization per job board
            
            # Extract job title
            title = soup.find('title')
            if title:
                data['job_title'] = title.text.strip()
            
            # Extract description
            job_desc = soup.find('div', {'class': ['job-description', 'description', 'content']})
            if job_desc:
                data['description'] = job_desc.get_text(strip=True)
            
            # Extract application URL
            apply_btn = soup.find('a', text=lambda x: x and 'apply' in x.lower())
            if apply_btn:
                data['application_url'] = apply_btn.get('href')
            
        except Exception as e:
            logger.error(f"Error extracting job data: {e}")
        
        return data


class CrawlWorker:
    """Worker that processes crawl tasks from the queue"""
    
    def __init__(self, worker_id: int, redis_client: redis.Redis):
        self.worker_id = worker_id
        self.redis = redis_client
        self.running = False
        self.company_crawler = CompanyCrawler()
        self.job_crawler = JobBoardCrawler('general')
    
    async def process_task(self, task_data: Dict[str, Any]) -> CrawlResult:
        """Process a single crawl task"""
        task = CrawlTask(**task_data)
        logger.info(f"Worker {self.worker_id} processing: {task.url}")
        
        # Choose crawler based on task type
        if task.metadata.get('type') == 'company':
            result = await self.company_crawler.crawl(task.url, **task.metadata)
        else:
            result = await self.job_crawler.crawl(task.url, **task.metadata)
        
        # Store result
        result_key = f"crawl_result:{task.task_id}"
        self.redis.setex(
            result_key,
            3600,  # 1 hour expiry
            json.dumps({
                'url': result.url,
                'success': result.success,
                'data': result.data_extracted,
                'crawl_time_ms': result.crawl_time_ms
            })
        )
        
        return result
    
    async def run(self):
        """Main worker loop"""
        self.running = True
        queue_name = config['redis']['key_prefix'] + 'crawl_queue'
        
        logger.info(f"Worker {self.worker_id} started")
        
        while self.running:
            try:
                # Blocking pop from queue
                task_data = self.redis.blpop(queue_name, timeout=1)
                if task_data:
                    _, task_json = task_data
                    task_dict = json.loads(task_json)
                    await self.process_task(task_dict)
                    
            except Exception as e:
                logger.error(f"Worker {self.worker_id} error: {e}")
                await asyncio.sleep(1)
        
        logger.info(f"Worker {self.worker_id} stopped")


class DistributedCrawler:
    """Main distributed crawler orchestrator"""
    
    def __init__(self, num_workers: int = 5):
        self.redis_client = redis.Redis(
            host=config['redis']['host'],
            port=config['redis']['port'],
            db=config['redis']['db'],
            decode_responses=True
        )
        self.num_workers = num_workers
        self.workers = []
        self.queue_name = config['redis']['key_prefix'] + 'crawl_queue'
    
    def add_task(self, url: str, task_type: str = 'general', 
                 priority: int = 0, metadata: Dict = None):
        """Add a crawl task to the queue"""
        task_id = hashlib.md5(f"{url}{time.time()}".encode()).hexdigest()[:12]
        task = {
            'url': url,
            'task_id': task_id,
            'priority': priority,
            'type': task_type,
            'metadata': metadata or {}
        }
        
        # Add to priority queue (higher number = higher priority)
        self.redis_client.zadd(
            f"{self.queue_name}:priority",
            {json.dumps(task): -priority}
        )
        
        logger.info(f"Added task {task_id} for {url}")
        return task_id
    
    async def start(self):
        """Start all workers"""
        logger.info(f"Starting {self.num_workers} workers...")
        
        for i in range(self.num_workers):
            worker = CrawlWorker(i, self.redis_client)
            self.workers.append(worker)
            asyncio.create_task(worker.run())
        
        # Start task distributor
        asyncio.create_task(self._distribute_tasks())
    
    async def _distribute_tasks(self):
        """Distribute tasks from priority queue to workers"""
        logger.info("Task distributor started")
        
        while True:
            try:
                # Get highest priority task
                tasks = self.redis_client.zrange(
                    f"{self.queue_name}:priority",
                    0, 0
                )
                
                if tasks:
                    task_json = tasks[0]
                    task = json.loads(task_json)
                    
                    # Add to worker queue
                    self.redis_client.lpush(self.queue_name, task_json)
                    
                    # Remove from priority queue
                    self.redis_client.zrem(
                        f"{self.queue_name}:priority",
                        task_json
                    )
                
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Distributor error: {e}")
                await asyncio.sleep(1)
    
    async def stop(self):
        """Stop all workers"""
        for worker in self.workers:
            worker.running = False
        logger.info("All workers stopped")


# Company URL generators for DFW area
class DFWCompanySource:
    """Sources for DFW tech companies"""
    
    @staticmethod
    def get_dfw_companies() -> List[str]:
        """Get URLs of DFW tech company lists"""
        return [
            "https://www.linkedin.com/directory/companies/tech/dallas/",
            "https://www.builtintexas.com/companies/tech/",
            "https://www.crunchbase.com/organizations.directory/technology/locations~region:dallas-fort-worth",
            # Add more sources
        ]
    
    @staticmethod
    def get_job_board_urls(city: str = "Dallas", state: str = "TX") -> List[str]:
        """Generate job board search URLs"""
        return [
            f"https://www.indeed.com/jobs?q=tech&l={city}%2C+{state}",
            f"https://www.linkedin.com/jobs/search?keywords=Tech&location={city}%2C+{state}",
            f"https://www.glassdoor.com/Job/jobs.htm?sc.keyword=Tech&locT=C&locI=1240",
            f"https://www.dice.com/jobs?l={city}%2C+{state}&q=technology",
        ]


# Usage example
async def main():
    """Example usage of the distributed crawler"""
    crawler = DistributedCrawler(num_workers=3)
    
    # Add some seed URLs
    for url in DFWCompanySource.get_job_board_urls():
        crawler.add_task(url, task_type='jobs', priority=0)
    
    await crawler.start()
    
    # Run for some time
    await asyncio.sleep(60)
    
    await crawler.stop()


if __name__ == "__main__":
    asyncio.run(main())
