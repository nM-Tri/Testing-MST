import streamlit as st
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import undetected_chromedriver as uc
import time
import random
import os
import zipfile
import shutil
import tempfile
import logging
import sys
import requests
from io import StringIO
import tempfile
import shutil
import cloudscraper
from bs4 import BeautifulSoup
from selenium_stealth import stealth

# --- Logging Configuration ---
class CustomFormatter(logging.Formatter):
    """Logging Formatter to add colors"""
    grey = "\x1b[38;21m"
    green = "\x1b[32;21m"
    yellow = "\x1b[33;21m"
    red = "\x1b[31;21m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    format_str = "%(asctime)s - %(levelname)s - %(message)s"

    FORMATS = {
        logging.DEBUG: grey + format_str + reset,
        logging.INFO: green + format_str + reset,
        logging.WARNING: yellow + format_str + reset,
        logging.ERROR: red + format_str + reset,
        logging.CRITICAL: bold_red + format_str + reset
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt, datefmt='%Y-%m-%d %H:%M:%S')
        return formatter.format(record)

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Clear existing handlers to avoid duplicates if re-run
if logger.hasHandlers():
    for handler in logger.handlers:
        handler.close()
    logger.handlers.clear()

# File Handler (No Color)
file_handler = logging.FileHandler("scraper.log", encoding='utf-8')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

# Stream Handler (Color)
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setFormatter(CustomFormatter())

logger.addHandler(file_handler)
logger.addHandler(stream_handler)
# --- Configuration ---
# --- Configuration ---
MASOTHUE_URL = "https://masothue.com"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/121.0"
]

def human_delay(min_seconds=1, max_seconds=3):
    """Sleeps for a random amount of time to mimic human behavior."""
    sleep_time = random.uniform(min_seconds, max_seconds)
    # Occasionally sleep longer to simulate reading/distraction
    if random.random() < 0.05: 
        sleep_time += random.uniform(1, 2)
    time.sleep(sleep_time)

def wait_for_element(driver, by, value, timeout=3, retries=1, retry_delay=2):
    """
    Waits for an element to be present.
    If not found, waits 'retry_delay' seconds and tries again 'retries' times.
    """
    for i in range(retries + 1):
        try:
            element = WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((by, value))
            )
            return element
        except Exception:
            if i < retries:
                logger.warning(f"Element '{value}' not found. Waiting {retry_delay}s before retry...")
                st.toast(f"Waiting {retry_delay}s for element...", icon="⏳")
                time.sleep(retry_delay)
            else:
                raise

def handle_cloudflare_turnstile(driver):
    """
    Attempts to handle Cloudflare Turnstile 'Verify you are human' check.
    """
    try:
        # Check for the turnstile iframe
        frames = driver.find_elements(By.TAG_NAME, "iframe")
        turnstile_frame = None
        
        # Strategy 1: Check by SRC
        for frame in frames:
            src = frame.get_attribute("src")
            if src and ("turnstile" in src or "challenges" in src):
                turnstile_frame = frame
                break
        
        # Strategy 2: If no obvious src, check content of iframes
        if not turnstile_frame:
            for frame in frames:
                try:
                    driver.switch_to.frame(frame)
                    if driver.find_elements(By.CSS_SELECTOR, "input[type='checkbox']"):
                        # Found a checkbox inside an iframe, likely the one
                        turnstile_frame = frame
                        driver.switch_to.default_content() # Switch back to switch properly later
                        break
                    driver.switch_to.default_content()
                except:
                    driver.switch_to.default_content()

        if turnstile_frame:
            logger.info("⚠️ Cloudflare Turnstile detected. Attempting to verify...")
            st.toast("Cloudflare Turnstile detected. Verifying...", icon="🤖")
            
            driver.switch_to.frame(turnstile_frame)
            human_delay(1, 2)
            
            # Click the checkbox
            try:
                # Try clicking the visual checkbox span or the label
                # Based on user HTML: <label class="cb-lb"><input type="checkbox"><span class="cb-i"></span>...</label>
                checkbox = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "label.cb-lb, span.cb-i, input[type='checkbox']"))
                )
                
                # Try standard click
                try:
                    checkbox.click()
                    logger.info("✅ Clicked Cloudflare checkbox (Standard).")
                except:
                    # Try JS click if standard fails
                    driver.execute_script("arguments[0].click();", checkbox)
                    logger.info("✅ Clicked Cloudflare checkbox (JS).")
                
                st.toast("Clicked verification checkbox.", icon="✅")
            except Exception as e:
                logger.warning(f"Could not find specific checkbox, clicking body: {e}")
                try:
                    driver.find_element(By.TAG_NAME, "body").click()
                except: pass
            
            driver.switch_to.default_content()
            human_delay(3, 5) # Wait for reload/redirect
            return True
    except Exception as e:
        logger.warning(f"Error handling Cloudflare: {e}")
        try:
            driver.switch_to.default_content()
        except: pass
    
    return False

def wait_for_element(driver, by, value, timeout=3, retries=1, retry_delay=2):
    """
    Waits for an element to be present.
    If not found, waits 'retry_delay' seconds and tries again 'retries' times.
    Also checks for Cloudflare during waits.
    """
    for i in range(retries + 1):
        try:
            element = WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((by, value))
            )
            return element
        except Exception:
            # Check for Cloudflare before retrying
            if handle_cloudflare_turnstile(driver):
                # If we handled a captcha, reset the loop or try again immediately
                logger.info("Cloudflare handled, retrying element wait...")
                time.sleep(3)
                continue

            if i < retries:
                logger.warning(f"Element '{value}' not found. Waiting {retry_delay}s before retry...")
                st.toast(f"Waiting {retry_delay}s for element...", icon="⏳")
                time.sleep(retry_delay)
            else:
                return False

def init_driver(extension_path=None, proxy=None, user_agent=None, proxy_auth_plugin=None):
    """Initializes the Undetected Chrome Driver with options."""
    chrome_options = uc.ChromeOptions()
    
    # Extension Setup
    extensions = []
    if proxy_auth_plugin:
        extensions.append(proxy_auth_plugin)
        
    if extension_path:
        if os.path.exists(extension_path):
            extensions.append(extension_path)
            st.toast(f"Loaded extension from: {extension_path}", icon="🧩")
        else:
            st.warning(f"Extension path not found: {extension_path}")
            
    if extensions:
        chrome_options.add_argument(f"--load-extension={','.join(extensions)}")

    # Proxy Setup (Simple IP:PORT)
    if proxy:
        chrome_options.add_argument(f'--proxy-server={proxy}')
        logger.info(f"Using Proxy: {proxy}")

    # Session Persistence
    # Use a local folder 'chrome_profile' in the current directory
    profile_dir = os.path.join(os.getcwd(), "chrome_profile")
    if not os.path.exists(profile_dir):
        os.makedirs(profile_dir)
    # uc handles user-data-dir slightly differently, but passing it as argument usually works
    chrome_options.add_argument(f"--user-data-dir={profile_dir}")
    
    # Anti-detection / Stability options
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--start-maximized")
    
    # Cloudflare Bypass Enhancements
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--disable-popup-blocking")
    
    # Initialize Driver
    driver = None
    try:
        # Try undetected_chromedriver first
        # Pin version to 142 to match current browser version (142.0.7444.175)
        logger.info("Attempting to launch undetected_chromedriver (v142)...")
        driver = uc.Chrome(options=chrome_options, version_main=142) 
    except Exception as e:
        logger.error(f"Failed to initialize UC driver: {e}")
        st.toast("UC Driver failed, falling back to standard Selenium...", icon="⚠️")
        
        # Fallback to standard Selenium
        try:
            logger.info("Attempting to launch standard Selenium WebDriver...")
            # Re-create options for standard selenium (uc options might be compatible but safer to be clean)
            std_options = Options()
            for arg in chrome_options.arguments:
                std_options.add_argument(arg)
            
            # Add experimental options that UC might have handled
            std_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            std_options.add_experimental_option('useAutomationExtension', False)
            
            driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=std_options)
        except Exception as e2:
            logger.error(f"Failed to initialize standard driver: {e2}")
            raise e2
        
    # Mask navigator.webdriver (Common for both)
    # --- Selenium Stealth ---
    try:
        stealth(driver,
            languages=["en-US", "en"],
            vendor="Google Inc.",
            platform="Win32",
            webgl_vendor="Intel Inc.",
            renderer="Intel Iris OpenGL Engine",
            fix_hairline=True,
        )
        logger.info("Applied selenium-stealth settings.")
    except Exception as e:
        logger.warning(f"Failed to apply selenium-stealth: {e}")

    # Additional manual masking
    try:
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    except Exception as e:
        logger.warning(f"Failed to mask navigator.webdriver: {e}")

    return driver

def check_ip(driver):
    """Checks and logs the current IP address."""
    try:
        logger.info("Checking current IP...")
        driver.get("https://api.ipify.org?format=json")
        time.sleep(1)
        ip_data = driver.find_element(By.TAG_NAME, "pre").text
        logger.info(f"🌍 Current IP: {ip_data}")
        st.toast(f"Current IP: {ip_data}", icon="🌍")
        return ip_data
    except Exception as e:
        logger.warning(f"Failed to check IP: {e}")
        return None

def scrape_company_details_cloudscraper(url, proxy_config=None):
    """Scrapes company details using cloudscraper (Fast Mode)."""
    try:
        logger.info(f"⚡ [Fast Mode] Fetching details via Cloudscraper: {url}")
        
        # Configure scraper
        # Configure scraper with more specific browser headers
        with cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'mobile': False
            }
        ) as scraper:
            # Add some common headers
            scraper.headers.update({
                'Accept-Language': 'en-US,en;q=0.9,vi;q=0.8',
                'Cache-Control': 'max-age=0',
                'Upgrade-Insecure-Requests': '1',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            })
            
            # Apply Proxy if available
            proxies = None
            if proxy_config:
                # proxy_config expected to be dict {'http': ..., 'https': ...} or string
                if isinstance(proxy_config, str):
                    proxies = {'http': proxy_config, 'https': proxy_config}
                elif isinstance(proxy_config, dict):
                    proxies = proxy_config
                    
            response = scraper.get(url, proxies=proxies)
            
            if response.status_code != 200:
                logger.warning(f"Cloudscraper failed with status {response.status_code}")
                return None
                
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract Data (Same logic as Selenium but using BS4)
            info = {
                "Tên công ty": "",
                "Mã số thuế": "",
                "Địa chỉ Thuế": "",
                "Địa chỉ": "",
                "Người đại diện": "",
                "Điện thoại": "",
                "Ngày hoạt động": "",
                "Quản lý bởi": "",
                "Loại hình DN": "",
                "Tình trạng": "",
                "Tên quốc tế": ""
            }
            
            # Title often contains Company Name
            if soup.select_one("h1.h1"):
                 info["Tên công ty"] = soup.select_one("h1.h1").get_text(strip=True)
            
            # Table parsing
            table = soup.select_one("table.table-taxinfo")
            if table:
                rows = table.select("tr")
                for row in rows:
                    cols = row.select("td")
                    if len(cols) == 2:
                        key = cols[0].get_text(strip=True)
                        val = cols[1].get_text(strip=True)
                        
                        # Clean up "Ẩn số điện thoại"
                        if "Ẩn số điện thoại" in val:
                            val = val.replace("Ẩn số điện thoại", "").strip()
                        
                        if "Mã số thuế" in key:
                            info["Mã số thuế"] = val
                        elif "Địa chỉ Thuế" in key:
                            info["Địa chỉ Thuế"] = val
                        elif "Địa chỉ" in key:
                            info["Địa chỉ"] = val
                        elif "Người đại diện" in key:
                            info["Người đại diện"] = val
                        elif "Điện thoại" in key:
                            info["Điện thoại"] = val
                        elif "Ngày hoạt động" in key:
                            info["Ngày hoạt động"] = val
                        elif "Quản lý bởi" in key:
                            info["Quản lý bởi"] = val
                        elif "Loại hình DN" in key:
                            info["Loại hình DN"] = val
                        elif "Tình trạng" in key:
                            info["Tình trạng"] = val
                        elif "Tên quốc tế" in key:
                            info["Tên quốc tế"] = val
                            
            return info
    except Exception as e:
        logger.error(f"Cloudscraper error: {e}")
        return None

def scrape_company_details(driver):
    """Scrapes details from a single company page."""
    info = {
        "Tên công ty": "",
        "Mã số thuế": "",
        "Địa chỉ Thuế": "",
        "Địa chỉ": "", # Often same as Tax Address
        "Người đại diện": "",
        "Điện thoại": "",
        "Ngày hoạt động": "",
        "Quản lý bởi": "",
        "Loại hình DN": "",
        "Tình trạng": "",
        "Tên quốc tế": ""
    }
    
    try:
        # Extract Company Name (usually h1)
        try:
            h1_elem = driver.find_element(By.TAG_NAME, "h1")
            info["Tên công ty"] = h1_elem.text.strip()
        except: pass

        # Parse the main tax info table
        try:
            # Wait for table to be present
            table = wait_for_element(driver, By.CSS_SELECTOR, "table.table-taxinfo", timeout=5)
            rows = table.find_elements(By.TAG_NAME, "tr")
            
            for row in rows:
                cols = row.find_elements(By.TAG_NAME, "td")
                if len(cols) >= 2:
                    # First col is label, Second is value
                    key = cols[0].text.strip()
                    
                    # Value extraction: Get text, but handle "Hide phone" button if present
                    # We can get innerText, but it might include button text.
                    # Best to get text of children if possible, or just replace known garbage.
                    val_elem = cols[1]
                    val = val_elem.text.strip()
                    
                    # Clean up "Ẩn số điện thoại" or similar
                    if "Ẩn số điện thoại" in val:
                        val = val.replace("Ẩn số điện thoại", "").strip()
                    
                    # Map keys
                    if "Mã số thuế" in key:
                        info["Mã số thuế"] = val
                    elif "Địa chỉ Thuế" in key:
                        info["Địa chỉ Thuế"] = val
                        if not info["Địa chỉ"]: info["Địa chỉ"] = val # Fallback
                    elif "Địa chỉ" in key and "Thuế" not in key: # Just "Địa chỉ"
                        info["Địa chỉ"] = val
                    elif "Người đại diện" in key:
                        info["Người đại diện"] = val
                    elif "Điện thoại" in key:
                        info["Điện thoại"] = val
                    elif "Ngày hoạt động" in key:
                        info["Ngày hoạt động"] = val
                    elif "Quản lý bởi" in key:
                        info["Quản lý bởi"] = val
                    elif "Loại hình DN" in key:
                        info["Loại hình DN"] = val
                    elif "Tình trạng" in key:
                        info["Tình trạng"] = val
                    elif "Tên quốc tế" in key:
                        info["Tên quốc tế"] = val

        except Exception as e:
            logger.warning(f"Error parsing table rows: {e}")
            
        # Fallback for Tax ID from H1 if table failed
        if not info["Mã số thuế"] and info["Tên công ty"]:
             try:
                parts = info["Tên công ty"].split('-', 1)
                if len(parts) >= 2 and parts[0].strip().isdigit():
                    info["Mã số thuế"] = parts[0].strip()
                    # Update name to be just the name part if desired, or keep full
                    # info["Tên công ty"] = parts[1].strip() 
             except: pass

        logger.info(f"Extracted Data: {info}")
        
    except Exception as e:
        logger.error(f"Error scraping details: {e}")
        
    return info

def scrape_masothue(driver, buyer_name, crawl_details=False, use_fast_mode=False, proxy_string=None):
    """Scrapes masothue.com for a given buyer name, handling multiple results."""
    results_list = []
    
    try:
        # Log IP before search (Per-Request Logging)
        check_ip(driver)
        
        logger.info(f"\n{'='*40}\n🔍 SEARCHING: {buyer_name}\n{'='*40}")
        
        # Try to find search box on current page to avoid reload
        try:
            search_box = driver.find_element(By.ID, "search")
        except:
            # If not found, go to home
            driver.get(MASOTHUE_URL)
            search_box = wait_for_element(driver, By.ID, "search", timeout=5, retries=1, retry_delay=10)

        search_box.clear()
        search_box.send_keys(buyer_name)
        search_box.send_keys(Keys.ENTER) 
        
        # Wait for page load
        human_delay(1, 2)
        
        # Check if we are on a search result page (list) or detail page
        is_detail_page = False
        try:
            driver.find_element(By.CSS_SELECTOR, "table.table-taxinfo")
            is_detail_page = True
        except:
            is_detail_page = False
            
        if is_detail_page:
            # Direct hit
            logger.info("Direct hit on detail page.")
            info = scrape_company_details(driver)
            results_list.append(info)
        else:
            # List of results
            try:
                # Try multiple selectors to find company links
                # Based on user HTML, results might be in a tab-pane or tax-listing div
                potential_items = [] # List of (href, text)
                seen_links = set()
                
                # Strategy 1: Look for h3 > a (Common for titles) inside specific containers
                selectors = [
                    "div.tax-listing h3 a",
                    "div.tax-listing a", 
                    "div#tab-products-1 h3 a",
                    "div#tab-products-1 a",
                    "h3 a", # Generic fallback
                    "table a" # Sometimes results are in a table
                ]
                
                elements = []
                for selector in selectors:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        # Filter out irrelevant links (e.g., navigation, ads)
                        # Company links usually don't have 'javascript' and are not empty
                        for elem in elements:
                            try:
                                href = elem.get_attribute("href")
                                text = elem.text.strip()
                                if href and "masothue.com" in href and "search" not in href and "google" not in href:
                                    # Filter irrelevant links
                                    IGNORED_SUBSTRINGS = [
                                        "/tra-cuu-ma-so-thue-theo-tinh/",
                                        "/tra-cuu-ma-so-thue-ca-nhan/",
                                        "/nganh-nghe/",
                                        "/dia-ban/",
                                        "/tu-khoa/",
                                        "/danh-ba-cong-ty/"
                                    ]
                                    if any(sub in href.lower() for sub in IGNORED_SUBSTRINGS):
                                        # logger.info(f"  ⚠️ Skipping category link: {href}")
                                        continue
                                    
                                    # Heuristic: Company links usually have a tax code (digits) in the slug
                                    # e.g. /0312345678-ten-cong-ty
                                    # Category links usually don't.
                                    # STRICTER CHECK: Must have at least 5 digits to be a tax code or valid ID
                                    digit_count = sum(c.isdigit() for c in href)
                                    if digit_count < 5:
                                        # logger.info(f"  ⚠️ Skipping non-company link (few digits): {href}")
                                        continue

                                    if href not in seen_links:
                                        potential_items.append((href, text))
                                        seen_links.add(href)
                            except:
                                pass # Ignore stale elements
                        
                        if potential_items:
                            break # Found some links using this selector, stop trying others to avoid noise
                
                # If still no links, try finding ALL links in the main content area (if identifiable)
                if not potential_items:
                    try:
                        main_content = driver.find_element(By.CSS_SELECTOR, "div.container") # Assuming bootstrap container
                        all_links = main_content.find_elements(By.TAG_NAME, "a")
                        for elem in all_links:
                            try:
                                href = elem.get_attribute("href")
                                text = elem.text.strip()
                                if href and "masothue.com" in href and len(href) > 30: # Simple heuristic
                                    if href not in seen_links:
                                        potential_items.append((href, text))
                                        seen_links.add(href)
                            except: pass
                    except: pass

                st.toast(f"Found {len(potential_items)} potential companies for '{buyer_name}'", icon="🔍")
                # logger.info(f"Found {len(potential_items)} links: {[item[0] for item in potential_items]}")
                for href, text in potential_items:
                    logger.info(f"  [+] FOUND LINK: {href} ({text})")
                
                if not crawl_details:
                     # Just return basic info if we are not crawling deep
                     # But user wants details, so we usually crawl deep
                     pass

                # Visit each link to get details
                for href, text in potential_items:
                    # Ensure full URL
                    if not href.startswith("http"):
                        href = "https://masothue.com" + href
                    
                    info = None
                    
                    # --- FAST MODE (Cloudscraper) ---
                    if use_fast_mode:
                        # Construct proxy config for cloudscraper
                        # If using manual list, we might need to pass the current proxy from driver? 
                        # Driver proxy is hard to extract reliably if it was set via args.
                        # For now, let's support it mainly for the "Rotating Proxy (Auth)" mode where we have the string.
                        
                        cs_proxy = None
                        if proxy_string:
                             # Format: host:port:user:pass -> http://user:pass@host:port
                             try:
                                 parts = proxy_string.split(':')
                                 if len(parts) == 4:
                                     h, p, u, pwd = parts
                                     cs_proxy = f"http://{u}:{pwd}@{h}:{p}"
                                 elif len(parts) == 2:
                                     cs_proxy = f"http://{proxy_string}"
                             except: pass
                        
                        info = scrape_company_details_cloudscraper(href, proxy_config=cs_proxy)
                        
                        if info:
                            logger.info("  ✅ Cloudscraper success.")
                        else:
                            logger.warning("  ⚠️ Cloudscraper failed. Falling back to Selenium.")
                    
                    # --- Fallback to Selenium ---
                    if not info:
                        try:
                            driver.get(href)
                            # human_delay(2, 4) # Wait for load
                            wait_for_element(driver, By.CSS_SELECTOR, "table.table-taxinfo", timeout=5, retries=1, retry_delay=10)
                            
                            info = scrape_company_details(driver)
                            # Ensure link is preserved if needed, though scrape_company_details gets data from page
                            info["Masothue Link"] = href
                            results_list.append(info)
                            human_delay(2, 5)
                        except Exception as e:
                            logger.warning(f"Error processing link {href}: {e}")
                            pass
                        
            except Exception as e:
                logger.error(f"Error parsing search results: {e}")

    except Exception as e:
        logger.error(f"Error scraping {buyer_name}: {e}")
        raise e # Re-raise exception to trigger retry in main loop
    
    return results_list

def is_company(name):
    """Checks if the name represents a company based on keywords."""
    if not isinstance(name, str):
        return False
    keywords = ["công ty", "tnhh", "doanh nghiệp", "chi nhánh", "cp", "cổ phần", "tập đoàn", "xí nghiệp", "hợp tác xã"]
    name_lower = name.lower()
    return any(keyword in name_lower for keyword in keywords)

def load_proxies(file_obj):
    """Loads proxies from a text file object."""
    proxies = []
    if file_obj is not None:
        stringio = file_obj.getvalue().decode("utf-8")
        for line in stringio.splitlines():
            line = line.strip()
            if line:
                proxies.append(line)
    return proxies

def validate_proxy(proxy):
    """Checks if a proxy is working by making a request to a test URL."""
    try:
        # Use a timeout to avoid hanging
        response = requests.get("https://www.google.com", proxies={"http": proxy, "https": proxy}, timeout=5)
        if response.status_code == 200:
            logger.info(f"✅ Proxy OK: {proxy}")
            return True
        else:
            logger.warning(f"❌ Proxy Failed (Status {response.status_code}): {proxy}")
            return False
    except Exception as e:
        logger.warning(f"❌ Proxy Connection Error: {proxy} - {e}")
        return False

def get_working_proxy(proxies, retries=3):
    """Finds a working proxy from the list."""
    if not proxies:
        return None
        
    for _ in range(retries):
        proxy = random.choice(proxies)
        if validate_proxy(proxy):
            return proxy
        else:
            logger.warning(f"Proxy {proxy} failed validation. Retrying...")
    
    return None

import json

def get_checkpoint_filename(input_filename):
    """Generates a checkpoint filename based on the input filename."""
    base_name = os.path.splitext(input_filename)[0]
    return f"checkpoint_{base_name}.json"

def save_checkpoint(input_filename, last_index, last_company, total_rows):
    """Saves the current progress to a checkpoint file."""
    checkpoint_file = get_checkpoint_filename(input_filename)
    data = {
        "input_filename": input_filename,
        "last_index": last_index,
        "last_company": last_company,
        "total_rows": total_rows,
        "timestamp": time.time()
    }
    try:
        with open(checkpoint_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logger.error(f"Failed to save checkpoint: {e}")

def load_checkpoint(input_filename):
    """Loads progress from a checkpoint file."""
    checkpoint_file = get_checkpoint_filename(input_filename)
    if os.path.exists(checkpoint_file):
        try:
            with open(checkpoint_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data
        except Exception as e:
            logger.error(f"Failed to load checkpoint: {e}")
    return None

# --- Streamlit App ---
st.set_page_config(page_title="Masothue Scraper", layout="wide")

st.title("🕵️ Masothue.com Scraper with Selenium")

st.markdown("""
**Instructions:**
1. Upload your Excel/CSV file.
2. (Optional) Upload a Chrome Extension (.zip).
3. Set "Initial Wait Time" to handle ads manually on first launch.
4. Click 'Start Scraping'.
""")

# Sidebar Configuration
with st.sidebar:
    st.header("Configuration")
    
    # Extension Upload
    extension_zip = st.file_uploader("Upload Chrome Extension (.zip)", type=["zip"], help="Upload a zipped Chrome extension folder.")
    extension_path = None
    
    if extension_zip:
        # Use a persistent directory for extensions
        ext_dir = os.path.join(os.getcwd(), "extracted_extensions")
        if not os.path.exists(ext_dir):
            os.makedirs(ext_dir)
            
        # Use filename to create a stable folder name (avoid re-extracting if possible, or just overwrite)
        # Sanitize filename
        safe_filename = "".join([c for c in extension_zip.name if c.isalpha() or c.isdigit() or c==' ' or c=='.']).rstrip()
        folder_name = os.path.splitext(safe_filename)[0]
        extract_path = os.path.join(ext_dir, folder_name)
        
        # Always extract to ensure fresh copy if user re-uploads same name
        # But to avoid issues, we can check if it exists. 
        # For now, let's just overwrite/extract.
        with zipfile.ZipFile(extension_zip, 'r') as zip_ref:
            zip_ref.extractall(extract_path)
            
        # Recursively find manifest.json
        manifest_path = None
        for root, dirs, files in os.walk(extract_path):
            if "manifest.json" in files:
                manifest_path = root
                break
        
        if manifest_path:
            extension_path = os.path.abspath(manifest_path)
            st.success(f"Extension ready: {os.path.basename(extension_path)}", icon="✅")
            # st.caption(f"Path: {extension_path}") # Debug info
        else:
            st.error("Invalid Extension: manifest.json not found in zip.")

    st.divider()
    
    st.divider()
    
    # Proxy Configuration
    st.sidebar.header("3. Proxy Settings")
    
    proxy_mode = st.sidebar.radio("Proxy Mode", ["No Proxy", "Manual List (File)", "Rotating Proxy (Auth)"])
    
    proxies = []
    use_proxy_rotation = False
    requests_per_proxy = 10
    
    # Rotating Proxy (Auth) Variables
    rot_host = ""
    rot_port = ""
    rot_user = ""
    rot_pass = ""
    use_local_ip_first = False
    proxy_string = ""

    if proxy_mode == "Manual List (File)":
        use_proxy_rotation = True
        uploaded_proxy_file = st.sidebar.file_uploader("Upload Proxy List (.txt)", type=["txt"])
        requests_per_proxy = st.sidebar.number_input("Requests per Proxy", min_value=1, value=10)
        
        if uploaded_proxy_file is not None:
            stringio = StringIO(uploaded_proxy_file.getvalue().decode("utf-8"))
            raw_proxies = stringio.read().splitlines()
            proxies = [p.strip() for p in raw_proxies if p.strip()]
            st.sidebar.success(f"Loaded {len(proxies)} proxies.")
            
            if st.sidebar.button("Check Proxies"):
                st.toast("Checking proxies... This may take a while.", icon="⏳")
                valid_proxies = []
                progress_bar = st.sidebar.progress(0)
                for i, p in enumerate(proxies):
                    if validate_proxy(p):
                        valid_proxies.append(p)
                    progress_bar.progress((i + 1) / len(proxies))
                
                proxies = valid_proxies
                st.sidebar.success(f"Found {len(proxies)} working proxies.")
                st.session_state.valid_proxies = proxies # Store in session
        
        # Manual Proxy Fallback
        manual_proxy = st.sidebar.text_input("Or Enter Manual Proxy (ip:port)", "")
        if manual_proxy:
            proxies = [manual_proxy]
            
    elif proxy_mode == "Rotating Proxy (Auth)":
        st.sidebar.warning("Rotating Proxy (Auth) mode has been removed.")


    st.sidebar.markdown("---")
    use_fast_mode = st.sidebar.checkbox("⚡ Fast Mode (Cloudscraper)", value=False, help="Use Cloudscraper for detail pages (Faster). Falls back to Selenium if it fails.")

    st.sidebar.markdown("---")
    if st.sidebar.button("🏥 Check Browser Health"):
        if 'driver' in st.session_state and st.session_state.driver:
            try:
                st.info("Checking browser health on bot.sannysoft.com...")
                st.session_state.driver.get("https://bot.sannysoft.com/")
                time.sleep(5)
                screenshot = st.session_state.driver.get_screenshot_as_png()
                st.image(screenshot, caption="Browser Health Check", use_container_width=True)
                st.success("Health check complete. Review the screenshot above.")
            except Exception as e:
                st.error(f"Health check failed: {e}")
        else:
            st.warning("Browser not started. Please start scraping or launch manually first.")

    # --- Main Content ---
    
    # Manual Browser Control
    if "driver" not in st.session_state:
        st.session_state.driver = None

    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("1. Launch Browser", type="primary"):
            if st.session_state.driver is not None:
                try:
                    st.session_state.driver.quit()
                    # Clean up proxy auth extension temp dir if it exists
                    if "proxy_auth_ext_dir" in st.session_state and os.path.exists(st.session_state.proxy_auth_ext_dir):
                        shutil.rmtree(st.session_state.proxy_auth_ext_dir)
                        del st.session_state.proxy_auth_ext_dir
                except: pass
            
            st.write("Launching Browser...")
            try:
                # Determine initial proxy settings
                initial_proxy = None
                initial_auth_plugin = None
                
                if proxy_mode == "Manual List (File)":
                    if proxies:
                        st.toast("Finding a working proxy...", icon="🔎")
                        initial_proxy = get_working_proxy(proxies, retries=10)
                        if initial_proxy:
                            st.toast(f"Starting with proxy: {initial_proxy}", icon="🛡️")
                        else:
                            st.error("Could not find a working proxy after multiple retries. Using a random one.")
                            initial_proxy = random.choice(proxies) if proxies else None
                elif proxy_mode == "Rotating Proxy (Auth)":
                    if use_local_ip_first:
                        initial_proxy = None # Start with local IP
                        st.info("Starting with Local IP first.")
                    elif rot_host and rot_port and rot_user and rot_pass:
                        st.session_state.proxy_auth_ext_dir = initial_auth_plugin # Store for cleanup
                        st.toast("Starting with authenticated proxy.", icon="🛡️")
                    else:
                        st.warning("Rotating Proxy (Auth) selected but credentials incomplete. Starting without proxy.")
                
                # Select random User-Agent
                ua = random.choice(USER_AGENTS)
                
                st.session_state.driver = init_driver(extension_path, proxy=initial_proxy, user_agent=ua, proxy_auth_plugin=initial_auth_plugin)
                
                # Check IP
                check_ip(st.session_state.driver)
                
                st.session_state.driver.get(MASOTHUE_URL)
                st.success("Browser Launched! Please handle ads/captchas now.")
            except Exception as e:
                st.error(f"Failed to launch: {e}")

    with col2:
        if st.button("Close Browser"):
            if st.session_state.driver:
                try:
                    st.session_state.driver.quit()
                    st.session_state.driver = None
                    st.success("Browser Closed.")
                except: pass
            else:
                st.warning("No browser open.")

    st.divider()
    
    # Filtering
    only_companies = st.checkbox("Only scrape Companies", value=True, help="Filter input to only include names containing 'Công ty', 'TNHH', etc.")
    crawl_details = st.checkbox("Crawl Detailed Info", value=False, help="If checked, visits each company page to get Tax ID, Address, etc. If unchecked, only gets Name and Link (Faster).")
    
    st.info("Note: Browser session is saved in 'chrome_profile' folder.")
    
    st.divider()
    if st.button("Test Browser & Extension"):
        st.write("Opening Test Browser...")
        if extension_path:
            st.write(f"Loading extension from: `{extension_path}`")
        else:
            st.warning("No extension loaded.")
            
        try:
            # For test, we use a temporary driver or the main one? 
            # Let's use a separate one to avoid conflict or just use the main one if available?
            # Safer to use a separate one for a quick test, or just tell user to use Launch.
            # User wanted a specific test button. Let's keep it independent but warn if main driver is open.
            
            test_driver = init_driver(extension_path)
            test_driver.get("https://www.google.com")
            st.success("Browser opened! Check 'chrome://extensions' to verify. Close browser to continue.")
            st.info("Waiting for you to close the browser...")
            while True:
                try:
                    _ = test_driver.window_handles
                    time.sleep(1)
                except:
                    break
            st.write("Test Finished.")
        except Exception as e:
            st.error(f"Test failed: {e}")

# File Upload
uploaded_file = st.file_uploader("Upload Input File (Excel/CSV)", type=["xlsx", "csv"])

if uploaded_file:
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
        
        st.write("### Preview Input Data")
        st.dataframe(df.head())
        
        if "Người mua bảo hiểm" not in df.columns:
            st.error("Error: Column 'Người mua bảo hiểm' not found in input file.")
        else:
            # Apply Filtering
            if only_companies:
                original_count = len(df)
                df = df[df["Người mua bảo hiểm"].apply(is_company)]
                filtered_count = len(df)
                st.warning(f"Filtered {original_count - filtered_count} rows. Processing {filtered_count} companies.")
                
                # Export filtered list
                try:
                    filtered_filename = "filtered_companies.csv"
                    df.to_csv(filtered_filename, index=False)
                    st.toast(f"Saved filtered list to {filtered_filename}")
                    logger.info(f"💾 Exported filtered list to {filtered_filename}")
                except Exception as e:
                    logger.error(f"Failed to export filtered list: {e}")
            
            # Reset Progress Button
            base_name = os.path.splitext(uploaded_file.name)[0]
            output_filename = f"scraped_results_{base_name}.csv"
            checkpoint_filename = get_checkpoint_filename(uploaded_file.name)
            
            if os.path.exists(output_filename) or os.path.exists(checkpoint_filename):
                if st.button("⚠️ Reset Progress (Delete Saved Data)"):
                    if os.path.exists(output_filename):
                        os.remove(output_filename)
                    if os.path.exists(checkpoint_filename):
                        os.remove(checkpoint_filename)
                    st.success("Progress reset! You can start from scratch.")
                    st.rerun()
            
            if st.button("2. Start Scraping", type="primary"):
                if st.session_state.driver is None:
                    st.error("Please click 'Launch Browser' first and handle any ads.")
                elif len(df) == 0:
                    st.error("No data to process after filtering.")
                else:
                    # --- Resume Logic ---
                    # Generate a stable filename for the output based on input filename
                    # We use a hash or just the name to ensure it's unique to this file
                    base_name = os.path.splitext(uploaded_file.name)[0]
                    output_filename = f"scraped_results_{base_name}.csv"
                    
                    # Check if progress exists (CSV)
                    processed_companies = set()
                    if os.path.exists(output_filename):
                        try:
                            existing_df = pd.read_csv(output_filename)
                            if "Người mua bảo hiểm" in existing_df.columns:
                                processed_companies = set(existing_df["Người mua bảo hiểm"].astype(str))
                                st.info(f"Found existing progress (CSV): {len(processed_companies)} companies already scraped.")
                        except Exception as e:
                            logger.warning(f"Could not read existing progress file: {e}")
                    
                    # Check for Checkpoint (JSON) - More accurate for position
                    checkpoint = load_checkpoint(uploaded_file.name)
                    start_index = 0
                    if checkpoint:
                        # Validate if it matches current file
                        if checkpoint.get("total_rows") == len(df):
                            start_index = checkpoint.get("last_index", -1) + 1
                            st.info(f"Found Checkpoint: Resuming from row {start_index + 1} (Company: {checkpoint.get('last_company')})")
                        else:
                            # Relaxed check: Warn but allow resumption if user confirms or just auto-resume
                            # For now, let's auto-resume but warn
                            start_index = checkpoint.get("last_index", -1) + 1
                            st.warning(f"Checkpoint found but total rows mismatch ({checkpoint.get('total_rows')} vs {len(df)}). Resuming from row {start_index + 1} anyway.")
                    
                    # Filter df
                    if start_index > 0:
                        # Resume by index
                        companies_to_scrape = df.iloc[start_index:]
                        st.warning(f"Resuming from row {start_index + 1}. Skipping first {start_index} rows.")
                    else:
                        # Fallback to set-based filtering if no valid checkpoint
                        companies_to_scrape = df[~df["Người mua bảo hiểm"].astype(str).isin(processed_companies)]
                        if len(processed_companies) > 0:
                             st.warning(f"Resuming based on CSV... Skipping {len(processed_companies)} rows.")
                    
                    if len(companies_to_scrape) == 0:
                        st.success("All companies in this file have already been scraped!")
                        st.dataframe(pd.read_csv(output_filename))
                        # Offer download
                        with open(output_filename, "rb") as f:
                            st.download_button(
                                label="Download Completed Results",
                                data=f,
                                file_name=output_filename,
                                mime='text/csv',
                            )
                        st.stop()
                    
                    if len(processed_companies) > 0:
                        st.warning(f"Resuming... Skipping {len(processed_companies)} rows. {len(companies_to_scrape)} left to scrape.")
                    
                    st.write("Starting Scraping...")
                    driver = st.session_state.driver
                    
                    # Check if driver is still alive
                    try:
                        _ = driver.title
                    except:
                        st.error("Browser seems to be closed. Please Launch Browser again.")
                        st.session_state.driver = None
                        st.stop()

                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    results = [] # Keep local results for display if needed, but main storage is file
                    
                    total_rows = len(companies_to_scrape)
                    
                    # Iterate over the filtered dataframe
                    for i, (index, row) in enumerate(companies_to_scrape.iterrows()):
                        # --- Proxy Rotation Logic ---
                        should_rotate = False
                        
                        if proxy_mode == "Manual List (File)":
                            if use_proxy_rotation and i > 0 and i % requests_per_proxy == 0:
                                should_rotate = True
                        elif proxy_mode == "Rotating Proxy (Auth)":
                            # Only rotate ONCE if we started with Local IP and hit the limit
                            if use_local_ip_first and i == local_ip_limit:
                                should_rotate = True
                                st.info("Switching from Local IP to Proxy...")
                        
                        if should_rotate:
                            st.toast("Rotating Proxy...", icon="🔄")
                            try:
                                driver.quit()
                            except: pass
                            
                            new_proxy = None
                            new_auth_plugin = None
                            
                            if proxy_mode == "Manual List (File)":
                                # Find new working proxy
                                new_proxy = get_working_proxy(proxies, retries=10)
                                if not new_proxy:
                                    logger.error("Failed to find working proxy during rotation.")
                                    st.error("Failed to find working proxy. Continuing with direct connection or stopping?")
                                    if proxies:
                                        new_proxy = random.choice(proxies)
                            
                            elif proxy_mode == "Rotating Proxy (Auth)":
                                # For rotating proxy, we just need to restart the driver with the SAME auth plugin
                                # But if we started with Local IP, we now need to switch to the Proxy
                                pass
                            
                            new_ua = random.choice(USER_AGENTS)
                            logger.info(f"Switching proxy/rotating IP...")
                            
                            # Re-initialize driver
                            driver = init_driver(extension_path, proxy=new_proxy, user_agent=new_ua, proxy_auth_plugin=new_auth_plugin)
                            st.session_state.driver = driver # Update session state
                            st.toast(f"Rotated IP/Proxy", icon="🛡️")
                            human_delay(2, 4)
                        # -----------------------------

                        buyer_name = row["Người mua bảo hiểm"]
                        status_text.text(f"Processing ({i + 1}/{total_rows}): {buyer_name}")
                        
                        # --- Retry Loop ---
                        current_results = [] # Initialize for this company
                        max_retries = 5
                        scraped_info_list = []
                        success = False
                        
                        for attempt in range(max_retries):
                            try:
                                # Scrape (Returns a list of dicts)
                                # Pass proxy_string if available for Cloudscraper usage
                                current_proxy_str = None
                                if proxy_mode == "Rotating Proxy (Auth)" and proxy_string:
                                    current_proxy_str = proxy_string
                                    
                                scraped_info_list = scrape_masothue(driver, buyer_name, crawl_details=crawl_details, use_fast_mode=use_fast_mode, proxy_string=current_proxy_str)
                                success = True
                                break # Success, exit retry loop
                            except Exception as e:
                                logger.warning(f"Attempt {attempt + 1}/{max_retries} failed for '{buyer_name}': {e}")
                                st.toast(f"Error scraping '{buyer_name}'. Retrying with new proxy...", icon="⚠️")
                                
                                if attempt < max_retries - 1:
                                    # Rotate Proxy and Retry
                                    try:
                                        driver.quit()
                                    except: pass
                                    
                                    retry_proxy = None
                                    retry_auth_plugin = None
                                    
                                    if proxy_mode == "Manual List (File)":
                                        retry_proxy = get_working_proxy(proxies, retries=5)
                                        if not retry_proxy and proxies:
                                            retry_proxy = random.choice(proxies)
                                    elif proxy_mode == "Rotating Proxy (Auth)":                                    
                                        new_ua = random.choice(USER_AGENTS)
                                    
                                    # Re-init driver
                                    try:
                                        driver = init_driver(extension_path, proxy=retry_proxy, user_agent=new_ua, proxy_auth_plugin=retry_auth_plugin)
                                        st.session_state.driver = driver
                                        
                                        # Force navigation to ensure we are not on blank page
                                        logger.info("Navigating to Masothue.com after retry...")
                                        
                                        # Check IP before navigating to target
                                        check_ip(driver)
                                        
                                        driver.get(MASOTHUE_URL)
                                        human_delay(2, 3)
                                    except Exception as e2:
                                        logger.error(f"Failed to restart driver during retry: {e2}")
                                        break # Fatal error during retry setup
                                    except Exception as init_error:
                                        logger.error(f"Failed to re-init driver or navigate: {init_error}")
                                        time.sleep(2)
                                else:
                                    logger.error(f"All retries failed for '{buyer_name}'")
                                    st.error(f"Failed to scrape '{buyer_name}' after {max_retries} attempts.")
                        
                        if not success:
                            # User requested to STOP if scraping fails, so they can resume later.
                            # We do NOT save this row to the CSV.
                            # Next time they run, this company will be in the 'unprocessed' list.
                            logger.error(f"🛑 Stopping scraping due to repeated failures for: {buyer_name}")
                            st.error(f"🛑 Scraping stopped due to repeated failures for '{buyer_name}'. Fix proxies and try again to resume.")
                            st.stop()
                        elif not scraped_info_list:
                            # If no results found, still add the original row with empty scraped data
                            row_data = row.to_dict()
                            # row_data["LinkedIn URL"] = construct_linkedin_url(buyer_name)
                            row_data["Ghi chú"] = "Không tìm thấy trong MST" # Explicit note
                            current_results.append(row_data)
                        else:
                            for info in scraped_info_list:
                                # Create a new row for each company found
                                row_data = row.to_dict()
                                row_data.update(info)
                                
                                # row_data["LinkedIn URL"] = construct_linkedin_url(buyer_name)
                                current_results.append(row_data)
                        
                        # --- Incremental Save ---
                        # Convert current company results to DF
                        current_df = pd.DataFrame(current_results)
                        
                        # Append to CSV
                        # If file doesn't exist, write header. If it does, skip header.
                        header = not os.path.exists(output_filename)
                        
                        # Retry logic for saving CSV (in case of file lock or temporary resource exhaustion)
                        for save_attempt in range(3):
                            try:
                                current_df.to_csv(output_filename, mode='a', header=header, index=False)
                                break
                            except Exception as save_error:
                                logger.warning(f"Failed to save CSV (Attempt {save_attempt+1}): {save_error}")
                                time.sleep(2)
                        else:
                            st.error(f"Critical Error: Could not save results to {output_filename} after 3 attempts.")
                        
                        # Save Checkpoint (JSON)
                        # Use the original index from the dataframe iteration
                        # i is the loop index, but we need the absolute index from the original DF
                        # index is the label from iterrows, which preserves original index if we didn't reset_index
                        # But companies_to_scrape might be a slice.
                        # If we resumed, companies_to_scrape is df.iloc[start_index:]
                        # So 'i' is relative to the slice.
                        # We need the absolute index relative to the FULL dataframe.
                        # If we used iloc slicing, 'index' (from iterrows) should be the original index label.
                        # Assuming default RangeIndex, 'index' is the row number.
                        
                        # However, to be safe with our load logic (start_index = last_index + 1),
                        # we should store the integer position.
                        # If companies_to_scrape is a slice, we can calculate current absolute position:
                        # absolute_index = start_index + i
                        
                        # Let's use the 'index' variable from iterrows if it's an integer, which it usually is for default DF.
                        # But if user uploaded file, index is RangeIndex(0, N).
                        
                        current_absolute_index = start_index + i
                        save_checkpoint(uploaded_file.name, current_absolute_index, buyer_name, total_rows)
                        # ------------------------
                        
                        human_delay(3, 7)
                        
                        progress_bar.progress((i + 1) / total_rows)
                    
                    status_text.text("Scraping Completed!")
                    
                    # Read back the full file for display and download
                    if os.path.exists(output_filename):
                        final_df = pd.read_csv(output_filename)
                        st.write("### Scraped Results (All)")
                        st.dataframe(final_df)
                        
                        # Download Button
                        csv = final_df.to_csv(index=False).encode('utf-8')
                        st.download_button(
                            label="Download Results as CSV",
                            data=csv,
                            file_name=output_filename,
                            mime='text/csv',
                        )
                
    except Exception as e:
        st.error(f"Error processing file: {e}")
