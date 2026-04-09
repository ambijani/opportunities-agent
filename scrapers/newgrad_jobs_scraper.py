from .jobright_scraper import JobrightScraper


class NewGradJobsScraper(JobrightScraper):
    parent_url = "https://www.newgrad-jobs.com/"
    source_name = "newgrad_jobs"
    minisite_type = "newgrad"
