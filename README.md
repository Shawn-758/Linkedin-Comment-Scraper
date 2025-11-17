# LinkedIn Comment Scraper

A robust, automated system to scrape LinkedIn profile links of users who comment on a specific person's posts. Built with Python and Playwright, this tool is designed for business development and recruiting workflows to identify active leads efficiently.

## 🚀 Features

* **Targeted Scraping:** Scrapes comments from a specific user's recent activity.
* **Precise Filtering:** Configurable lookback period (e.g., past 7 days, 30 days). Uses accurate URN-based timestamp extraction.
* **Robust Automation:** Uses Playwright to handle LinkedIn's dynamic JavaScript loading and infinite scrolling.
* **Headline Scraping:** Optionally visits each commenter's profile to extract their headline (e.g., "Recruiter at Google").
* **Resilience:** Handles login sessions via cookies, detects "no posts" scenarios, and manages rate limiting with human-like delays.
* **Maintainability:** All CSS selectors are isolated in `selectors.json` for easy updates if LinkedIn changes its UI.
* **Docker Support:** Includes a Dockerfile for containerized deployment.

## 🛠️ Setup Instructions and Authentication

### Prerequisites
* Python 3.8+
* A LinkedIn account

### 1. Installation

Clone the repository and install the required packages.

* git clone (https://github.com/shawn-758/linkedin-comment-scraper.git)
* cd linkedin-comment-scraper
* pip install -r requirements.txt
* playwright install chromium

(Note: You may need to use pip3 and python3 depending on your system)


### 2. Add Your LinkedIn Cookie

This tool uses your browser's session cookie to authenticate safely, avoiding 2FA and bot detection.

#### i. Rename the Example File: Rename cookies.json.example to cookies.json.

#### ii. Find Your Cookie:

* Log in to LinkedIn on your regular Chrome/Edge browser.

* Open Developer Tools (Right-click > Inspect).

* Go to the Application tab.

* On the left, go to Storage > Cookies > https://www.linkedin.com.

* Copy the Value: In the filter box, type li_at.

* Click on the li_at cookie in the list.

* Copy the entire Cookie Value (it's a very long string).

#### iii.Paste the Value: 

* Open the cookies.json file you just renamed.

* Paste your long cookie value, replacing the PASTE_YOUR_li_at_COOKIE_VALUE_HERE placeholder.

### Important: The .gitignore file is already set up to ignore cookies.json, so you will never accidentally commit your personal session cookie.



## 🏃‍♂️ How to Run

Once your cookies.json file is set up, you are ready to run the script.

* Scrape a Single Profile (Basic)

This command scrapes comments from the last 7 days and outputs a simple list of profile URLs. Replace the placeholder with your target's profile URL.

```
python main.py --profile-url "[https://www.linkedin.com/in/TARGET-PROFILE-USERNAME](https://www.linkedin.com/in/TARGET-PROFILE-USERNAME)" --days 7
 ```

* Scrape a Single Profile (Advanced)

* This scrapes from the last 40 days

```python main.py --profile-url "[https://www.linkedin.com/in/TARGET-PROFILE-USERNAME](https://www.linkedin.com/in/TARGET-PROFILE-USERNAME)" --days 40```


#### Output

* The results will be saved in the output/ folder, automatically named after the profile (e.g., output/TARGET-PROFILE-USERNAME.csv).
