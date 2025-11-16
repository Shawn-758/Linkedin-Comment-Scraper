import json
import logging
import re
from datetime import datetime, timedelta
from playwright.async_api import Page, TimeoutError, Locator
from utils import clean_profile_url, parse_post_time, EMOJIS

class LinkedinScraper:
    """
    A class to encapsulate the scraping logic for LinkedIn.
    """

    def __init__(self, page: Page, days_limit: int, selector_file: str):
        self.page = page
        self.days_limit = timedelta(days=days_limit)
        self.seen_post_links = set()

        # Load selectors from the external JSON file
        try:
            with open(selector_file, 'r') as f:
                self.selectors = json.load(f)
        except FileNotFoundError:
            logging.error(f"Selector file not found: {selector_file}")
            raise
        except json.JSONDecodeError:
            logging.error(f"Error decoding JSON from selector file: {selector_file}")
            raise
        except Exception as e:
            logging.error(f"An unexpected error occurred while loading selectors: {e}")
            raise

    async def check_login(self) -> bool:
        """
        Verifies that the user is logged in by checking for a known element on the feed.
        """
        try:
            logging.info("Checking for successful login...")
            await self.page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=20000)
            await self.page.wait_for_selector(self.selectors["feed_page"], timeout=15000)
            return True
        except TimeoutError:
            logging.error("Login check failed. Could not find feed page element.")
            return False

    async def get_post_links(self, profile_url: str) -> list[str]:
        """
        Gets all post permalinks from a user's activity page within the time limit.
        """
        activity_url = f"{profile_url.rstrip('/')}/recent-activity/all/"
        logging.info(f"Navigating to activity page: {activity_url}")
        await self.page.goto(activity_url, wait_until="domcontentloaded", timeout=20000)

        try:
            # Wait for the first post to appear, which is a more reliable signal
            # than waiting for the container.
            logging.info("Waiting for post feed to load...")
            await self.page.wait_for_selector(
                self.selectors["post_list_item"], 
                state="attached", 
                timeout=15000
            )
            logging.info("Post feed loaded.")
        except TimeoutError:
            logging.warning("Activity page content did not load in time. The user may have no posts or the page structure changed.")
            return []

        post_links = []
        keep_scrolling = True
        
        while keep_scrolling:
            # Get all post items currently visible
            posts = self.page.locator(self.selectors["post_list_item"])
            
            post_count = await posts.count()
            if post_count == 0:
                logging.info("No posts found on the page.")
                break

            logging.info(f"Found {post_count} post elements on page. Processing...")

            for i in range(post_count):
                post = posts.nth(i)
                try:
                    link_element = post.locator(self.selectors["post_timestamp_and_link"])
                    
                    if await link_element.count() > 0:
                        href = await link_element.get_attribute("href")
                        time_str = await link_element.inner_text()
                        
                        if href and not href.startswith("https://"):
                            href = f"https://www.linkedin.com{href}"
                        
                        if href:
                            href = href.split("?")[0]
                        
                        if not href in self.seen_post_links:
                            self.seen_post_links.add(href)

                            time_str = time_str.strip()
                            post_age = parse_post_time(time_str)
                            
                            if post_age is None:
                                logging.warning(f"Could not parse timestamp: '{time_str}' for post {href}")
                                continue

                            if post_age <= self.days_limit:
                                post_links.append(href)
                            else:
                                logging.info(f"  -> Found post older than {self.days_limit} ({time_str}). Stopping scroll.")
                                keep_scrolling = False
                                break 
                except Exception as e:
                    logging.warning(f"  -> Error processing post: {e}")
                    continue

            if not keep_scrolling:
                break 
            
            logging.info(f"  -> Scrolling to load more posts... (Found {len(post_links)} so far)")
            await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            
            try:
                await self.page.wait_for_timeout(3000) 
            except TimeoutError:
                logging.info("  -> Page load timeout while scrolling. Assuming end of feed.")
                break

        return list(set(post_links)) # Return unique links

    async def _get_post_details(self, post: Locator) -> (str, str):
        """Extracts link and timestamp from a post locator."""
        try:
            link_element = post.locator(self.selectors["post_timestamp_and_link"])
            href = await link_element.get_attribute("href")
            time_str = await link_element.inner_text()
            return href, time_str
        except (TimeoutError, AttributeError):
            return None, None


    async def get_commenters_from_post(self, post_url: str) -> set[str]:
        """
        Gets all unique commenter profile URLs from a single post page.
        """
        await self.page.goto(post_url, wait_until="domcontentloaded", timeout=20000)

        # Wait for the comment section to load
        try:
            await self.page.wait_for_selector(self.selectors["comment_section"], timeout=10000)
        except TimeoutError:
            logging.warning("  -> No comment section found on this post.")
            return set()

        # Click "load more comments" button until it disappears
        while True:
            try:
                load_more_button = self.page.locator(self.selectors["load_more_comments_button"]).first
                if await load_more_button.is_visible():
                    await load_more_button.click()
                    # Add a small delay for comments to load
                    await self.page.wait_for_timeout(1000) 
                else:
                    break
            except (TimeoutError, Error):
                break
        
        # Scrape commenter links
        commenter_links = await self.page.locator(self.selectors["commenter_link"]).all()
        commenter_urls = set()
        for link in commenter_links:
            href = await link.get_attribute("href")
            if href:
                cleaned_url = clean_profile_url(href)
                if cleaned_url:
                    commenter_urls.add(cleaned_url)

        return commenter_urls

    async def get_profile_headlines(self, profile_urls: set[str]) -> list[dict]:
        results = []
        for url in profile_urls:
            try:
                await self.page.goto(url, wait_until="domcontentloaded", timeout=15000)
                headline_element = self.page.locator(self.selectors["profile_headline"]).first
                headline = await headline_element.inner_text(timeout=5000)
                results.append({"profile_url": url, "headline": headline.strip()})
            except (TimeoutError, Error) as e:
                logging.warning(f"  -> Could not scrape headline for {url}. Error: {e}")
                results.append({"profile_url": url, "headline": "ERROR: Could not scrape"})
        return results