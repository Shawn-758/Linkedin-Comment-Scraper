import argparse
import asyncio
import json
import logging
import os
import re
import tempfile
import traceback  # <-- ADD THIS LINE
from playwright.async_api import async_playwright, Error
from scraper import LinkedinScraper
import utils
from utils import EMOJIS

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)


def get_profile_name_from_url(url: str) -> str:
    """Extracts a clean name from a profile URL for filenames."""
    try:
        match = re.search(r"\/in\/([a-zA-Z0-9-]+)", url)
        if match:
            return match.group(1)
    except Exception:
        pass
    # Fallback
    return url.replace("https://", "").replace("www.", "").replace("linkedin.com", "").replace("/", "_")


async def main(args):
    """
    Main asynchronous function to run the scraper.
    """
    logging.info(f"{EMOJIS['rocket']} Starting the LinkedIn Comment Scraper...")

    # --- Validate Inputs ---
    if not os.path.exists(args.cookie_file):
        logging.error(f"{EMOJIS['cross_mark']} Cookie file not found: {args.cookie_file}")
        return
    if not os.path.exists(args.selector_file):
        logging.error(f"{EMOJIS['cross_mark']} Selector file not found: {args.selector_file}")
        return

    # --- Get Target URLs ---
    target_urls = []
    if args.profile_file:
        if not os.path.exists(args.profile_file):
            logging.error(f"{EMOJIS['cross_mark']} Profile file not found: {args.profile_file}")
            return
        with open(args.profile_file, 'r') as f:
            target_urls = [line.strip() for line in f if line.strip() and line.startswith("http")]
        logging.info(f"Loaded {len(target_urls)} profiles from {args.profile_file}")
    else:
        target_urls = [args.profile_url]

    # --- Ensure Dirs Exist ---
    os.makedirs(args.output_dir, exist_ok=True)
    os.makedirs(args.state_dir, exist_ok=True)

    # --- Create a temporary directory for the user profile ---
    with tempfile.TemporaryDirectory() as user_data_dir:
        async with async_playwright() as p:
            browser = None
            context = None
            try:
                context = await p.chromium.launch_persistent_context(
                    user_data_dir,
                    headless=args.headless,
                    slow_mo=50,
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
                    viewport={"width": 1920, "height": 1080},
                    args=[
                        "--disable-extensions",
                        "--disable-blink-features=AutomationControlled",
                        "--start-maximized",
                    ],
                )
                
                logging.info(f"{EMOJIS['cookie']} Loading cookies from {args.cookie_file}...")
                await context.add_cookies(utils.load_cookies(args.cookie_file))

                page = context.pages[0] if context.pages else await context.new_page()

                # --- Block bot-detection scripts ---
                await page.route(re.compile(r"protechts\.net"), lambda route: route.abort())

                def log_console_message(msg):
                    logging.info(f"🧑‍💻 BROWSER LOG: {msg.text}")

                # Attach the logger to the page's 'console' event
                page.on("console", log_console_message)
                scraper = LinkedinScraper(page, args.days, args.selector_file)

                # Check login
                if not await scraper.check_login():
                    logging.error(f"{EMOJIS['cross_mark']} Login failed. Cookies might be expired.")
                    return
                
                logging.info(f"{EMOJIS['check_mark']} Login successful.")

                # --- SAVE SUCCESSFUL COOKIES ---
                logging.info("Saving new, successful cookies to disk...")
                try:
                    new_cookies = await context.cookies()
                    with open(args.cookie_file, 'w') as f:
                        json.dump(new_cookies, f, indent=2)
                    logging.info(f"Successfully saved new cookies to {args.cookie_file}.")
                except Exception as e:
                    logging.warning(f"Could not save new cookies: {e}")


                # --- Main Profile Loop ---
                for i, base_url in enumerate(target_urls):
                    profile_name = get_profile_name_from_url(base_url)
                    logging.info(f"\n{'-'*50}\n{EMOJIS['rocket']} Processing profile {i+1}/{len(target_urls)}: {profile_name}\n{'-'*50}")

                    # --- Define State/Output Files ---
                    output_file = os.path.join(args.output_dir, f"{profile_name}.{args.format}")
                    posts_state_file = os.path.join(args.state_dir, f"{profile_name}_posts.json")
                    
                    all_commenter_results = []
                    try:
                        # --- 1. Get Post Links (with Checkpointing) ---
                        post_links = utils.load_state_json(posts_state_file)
                        if post_links is None:
                            logging.info(f"{EMOJIS['search']} No state file found. Scraping post links from scratch...")
                            post_links = await scraper.get_post_links(base_url)
                            if not post_links:
                                logging.warning("⚠️ No posts found for this user. Skipping.")
                                continue
                            utils.save_state_json(post_links, posts_state_file)
                            logging.info(f"Found {len(post_links)} posts. Saved links to state file.")
                        else:
                            logging.info(f"Loaded {len(post_links)} post links from state file.")

                        # --- 2. Load Existing Results ---
                        all_commenter_results = utils.load_results(output_file)
                        all_commenter_urls = {res['profile_url'] for res in all_commenter_results if 'profile_url' in res}
                        logging.info(f"Loaded {len(all_commenter_urls)} existing commenters from {output_file}.")

                        # --- 3. Scrape Commenters (Post by Post) ---
                        posts_to_process = list(post_links) # Copy to modify
                        for j, post_link in enumerate(posts_to_process):
                            logging.info(f"\n--- Processing post {j+1}/{len(posts_to_process)} ---")
                            logging.info(f"  -> URL: {post_link}")

                            # Scrape commenters from the current post
                            commenter_urls = await scraper.get_commenters_from_post(post_link)
                            new_commenter_urls = commenter_urls - all_commenter_urls
                            logging.info(f"  -> Found {len(commenter_urls)} total commenters ({len(new_commenter_urls)} new).")

                            if not new_commenter_urls:
                                continue

                            # Scrape headlines if enabled
                            if args.scrape_headlines:
                                new_results = await scraper.get_profile_headlines(new_commenter_urls)
                            else:
                                new_results = [{"profile_url": url, "headline": ""} for url in new_commenter_urls]

                            all_commenter_results.extend(new_results)
                            all_commenter_urls.update(new_commenter_urls)

                            # Save incrementally if enabled
                            if args.incremental_save:
                                utils.append_results(new_results, output_file, args.format)
                                logging.info(f"  -> Incrementally saved {len(new_results)} new commenters.")
                    
                    finally:
                        # --- Final Save (if not incremental) ---
                        if not args.incremental_save and all_commenter_results:
                            utils.save_results(all_commenter_results, output_file, args.format)
                            logging.info(f"{EMOJIS['disk']} Saved {len(all_commenter_results)} total commenters to {output_file}.")
                        
                        # --- Cleanup ---
                        if os.path.exists(posts_state_file):
                            os.remove(posts_state_file)
                            logging.info(f"Removed state file: {posts_state_file}")


            except Error as e:
                logging.error(f"{EMOJIS['cross_mark']} A Playwright error occurred: {e}")
            except Exception as e:
                logging.error(f"{EMOJIS['cross_mark']} An unexpected error occurred: {e}")
                logging.error(traceback.format_exc())
            finally:
                if context:
                    await context.close()
                logging.info(f"{EMOJIS['wave']} Scraper finished.")


def parse_args():
    """
    Parses command-line arguments.
    """
    parser = argparse.ArgumentParser(description="LinkedIn Comment Scraper")
    
    # --- Input Group ---
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "-u", "--profile-url", type=str,
        help="The full LinkedIn profile URL of the target person.",
    )
    group.add_argument(
        "-f", "--profile-file", type=str,
        help="Path to a .txt file containing multiple profile URLs (one per line).",
    )

    # --- Output Group ---
    parser.add_argument(
        "-o", "--output-dir", type=str, default="output",
        help="Directory to save results (default: output).",
    )
    parser.add_argument(
        "--format", type=str, choices=['csv', 'json'], default='csv',
        help="Output format (default: csv)."
    )

    # --- Config Group ---
    parser.add_argument(
        "-d", "--days", type=int, default=7,
        help="The time range in days to scrape posts from (default: 7).",
    )
    parser.add_argument(
        "-c", "--cookie-file", type=str, default="cookies.json",
        help="Path to the cookies.json file (default: cookies.json).",
    )
    parser.add_argument(
        "-s", "--selector-file", type=str, default="selectors.json",
        help="Path to the selectors.json file (default: selectors.json).",
    )
    
    # --- Feature Flags ---
    parser.add_argument(
        "--headless", action=argparse.BooleanOptionalAction, default=True,
        help="Run the browser in headless mode (default: True). Use --no-headless for debugging.",
    )
    parser.add_argument(
        "--scrape-headlines", action="store_true",
        help="Enable scraping of commenter headlines. (Increases time and risk)",
    )
    
    # --- Checkpointing ---
    parser.add_argument(
        "--state-dir", type=str, default="output/state",
        help="Directory to store checkpointing state files (default: output/state).",
    )
    parser.add_argument(
        "--incremental-save", action="store_true",
        help="Save results incrementally after each post is scraped.",
    )
    
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(main(args))