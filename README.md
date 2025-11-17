# LinkedIn Comment Scraper

A robust, automated system to scrape LinkedIn profile links of users who comment on a specific person's posts. Built with Python and Playwright, this tool is designed for business development and recruiting workflows to identify active leads efficiently.

## 🚀 Features

* **Targeted Scraping:** Scrapes comments from a specific user's recent activity.
* **Precise Filtering:** Configurable lookback period (e.g., past 7 days, 30 days). Uses accurate URN-based timestamp extraction.
* **Robust Automation:** Uses Playwright to handle LinkedIn's dynamic JavaScript loading and infinite scrolling.
* **Headline Scraping:** Optionally visits each commenter's profile to extract their headline (e.g., "Recruiter at Google").
* **Resilience:** Handles login sessions via cookies, detects "no posts" scenarios, and manages rate limiting with human-like delays.
* **Maintainability:** All CSS selectors are isolated in `selectors.json` for easy updates if LinkedIn changes its UI.

## 🛠️ Setup Instructions

### Prerequisites
* Python 3.8+
* A LinkedIn account

### 1. Installation
Clone the repository and install the dependencies:

```bash
git clone [https://github.com/your-username/linkedin-comment-scraper.git](https://github.com/your-username/linkedin-comment-scraper.git)
cd linkedin-comment-scraper
pip install -r requirements.txt
playwright install chromium
