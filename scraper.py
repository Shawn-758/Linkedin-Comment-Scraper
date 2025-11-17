import logging
import re
import json
import asyncio
from datetime import datetime, timedelta, timezone
from playwright.async_api import Page, TimeoutError, Locator
from utils import clean_profile_url, get_timestamp_from_urn, EMOJIS # <-- IMPORTED NEW FUNCTION

class LinkedinScraper:
    """
    A class to encapsulate the scraping logic for LinkedIn.
    """

    def __init__(self, page: Page, days_limit: int, selector_file: str):
        self.page = page
        self.days_limit_td = timedelta(days=days_limit)
        self.days_limit_int = days_limit
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
            await self.page.wait_for_selector(self.selectors["feed_page"], timeout=180000) # 3 min timeout for manual login
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

        # --- REMOVED THE PAUSE ---
        
        try:
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
        now = datetime.now(timezone.utc)
        
        while keep_scrolling:
            posts = self.page.locator(self.selectors["post_list_item"])
            
            post_count = await posts.count()
            if post_count == 0:
                logging.info("No posts found on the page.")
                break

            logging.info(f"Found {post_count} post elements on page. Processing...")
            new_posts_found = False

            for i in range(post_count):
                post = posts.nth(i)
                try:
                    # --- *** NEW LOGIC: Get URN from the post element itself *** ---
                    post_urn = await post.get_attribute("data-urn")
                    # --- *** ---

                    if post_urn:
                        # Build the permalink from the URN
                        post_id = post_urn.split(":")[-1]
                        clean_url = f"https://www.linkedin.com/feed/update/urn:li:activity:{post_id}/"

                        if clean_url in self.seen_post_links:
                            continue # Already processed this post
                        
                        self.seen_post_links.add(clean_url)
                        new_posts_found = True

                        # --- *** NEW LOGIC: Get timestamp from URN *** ---
                        post_timestamp = get_timestamp_from_urn(post_urn)
                        if post_timestamp is None:
                            logging.warning(f"  -> Could not parse timestamp from URN {post_urn}. Skipping.")
                            continue
                        
                        post_age_td = now - post_timestamp
                        # --- *** ---

                        if post_age_td <= self.days_limit_td:
                            post_links.append(clean_url)
                        else:
                            logging.info(f"  -> Reached post older than {self.days_limit_int} days ({post_age_td.days} days old). Stopping scroll.")
                            keep_scrolling = False
                            break
                    else:
                        logging.warning(f"  -> Found post element but could not extract data-urn. Skipping. (Post index: {i})")

                except Exception as e:
                    logging.error(f"  -> Error processing a post element: {e}")

                if not keep_scrolling:
                    break 
            
            if not keep_scrolling:
                break 
            
            if not new_posts_found and post_count > 0:
                logging.info("  -> No new posts found in the last scroll. Reached end.")
                break

            logging.info(f"  -> Scrolling to load more posts... (Found {len(post_links)} so far)")
            await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            
            try:
                await self.page.wait_for_timeout(3000) 
            except TimeoutError:
                logging.info("  -> Page load timeout while scrolling. Assuming end of feed.")
                break

        return list(set(post_links)) # Return unique links

    # --- THIS FUNCTION IS NO LONGER USED, BUT WE LEAVE IT ---
    async def _get_post_link(self, post: Locator) -> str | None:
        """Extracts link from a post locator."""
        try:
            link_element = post.locator(self.selectors["post_link"]).first
            href = await link_element.get_attribute("href", timeout=1000)
            return href
        except Exception:
            return None


    async def get_commenters_from_post(self, post_url: str) -> set[str]:
        """
        Gets all unique commenter profile URLs from a single post page.
        """
        await self.page.goto(post_url, wait_until="domcontentloaded", timeout=20000)

        try:
            await self.page.wait_for_selector(self.selectors["comment_section"], timeout=10000)
        except TimeoutError:
            logging.warning(f"  -> No comment section found on this post. Skipping.")
            return set()

        while True:
            try:
                load_more_button = self.page.locator(self.selectors["load_more_comments_button"]).first
                if await load_more_button.is_visible():
                    await load_more_button.click()
                    await self.page.wait_for_timeout(1000) 
                else:
                    break
            except Exception:
                break
        
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
            except Exception as e:
                logging.warning(f"  -> Could not scrape headline for {url}. Error: {e}")
                results.append({"profile_url": url, "headline": "ERROR: Could not scrape"})
        return results