
Web Scraper Tool

Provides agents with the ability to fetch content from web pages.

This tool should handle HTTP requests, parse HTML content, and extract
relevant information. It should also manage things like headers, sessions,
and respect robots.txt policies.

Potential Functions:
- get_html(url)
- get_text_content(url)
- find_elements(url, css_selector)


import requests
from bs4 import BeautifulSoup

class WebScraper:
    def get_html(self, url: str) -> str:
        """
        Fetches the full HTML content of a given URL.
        """
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            return f"Error fetching URL: {e}"

    def get_text_content(self, url: str) -> str:
        """
        Fetches the text content of a web page, stripping HTML tags.
        """
        html = self.get_html(url)
        if html.startswith("Error"):
            return html
        
        soup = BeautifulSoup(html, 'html.parser')
        return soup.get_text(separator='\n', strip=True)

