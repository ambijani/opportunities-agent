from .jobright_scraper import JobrightScraper


class InternListScraper(JobrightScraper):
    parent_url = "https://www.intern-list.com/"
    source_name = "intern_list"
    minisite_type = "intern-list"
