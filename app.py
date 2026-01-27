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
import logging
import sys
from bs4 import BeautifulSoup

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
                return False

def init_driver(user_agent=None):
    """Initializes the Undetected Chrome Driver with options."""
    chrome_options = uc.ChromeOptions()
    
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
        
    # Additional manual masking
    try:
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    except Exception as e:
        logger.warning(f"Failed to mask navigator.webdriver: {e}")

    return driver

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

def scrape_masothue(driver, buyer_name, crawl_details=False):
    """Scrapes masothue.com for a given buyer name, handling multiple results.
    Returns (results_list, is_empty_result)
    """
    results_list = []
    is_empty_result = False
    
    try:
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
                            # Check if found links are ONLY the excluded navigation links
                            excluded_urls = [
                                "https://masothue.com/tra-cuu-ma-so-thue-theo-tinh/",
                                "https://masothue.com/tra-cuu-ma-so-thue-ca-nhan/"
                            ]
                            all_found_urls = [item[0] for item in potential_items]
                            
                            # If all found URLs are in the excluded list, mark as empty result
                            if all(url in excluded_urls for url in all_found_urls):
                                logger.info(f"  ⚠️ Only navigation links found for '{buyer_name}'. Skipping.")
                                is_empty_result = True
                                potential_items = [] # Clear them so we don't visit them
                            
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
    
    return results_list, is_empty_result

def is_company(name):
    """Checks if the name represents a company based on keywords."""
    if not isinstance(name, str):
        return False
    keywords = ["công ty", "tnhh", "doanh nghiệp", "chi nhánh", "cp", "cổ phần", "tập đoàn", "xí nghiệp", "hợp tác xã"]
    name_lower = name.lower()
    return any(keyword in name_lower for keyword in keywords)

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
2. Click 'Launch Browser'.
3. Click 'Start Scraping'.
""")

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
            except: pass
        
        st.write("Launching Browser...")
        try:
            # Select random User-Agent
            ua = random.choice(USER_AGENTS)
            
            st.session_state.driver = init_driver(user_agent=ua)
            
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
                        buyer_name = row["Người mua bảo hiểm"]
                        status_text.text(f"Processing ({i + 1}/{total_rows}): {buyer_name}")
                        
                        # --- Retry Loop ---
                        current_results = [] # Initialize for this company
                        max_retries = 3
                        scraped_info_list = []
                        success = False
                        
                        for attempt in range(max_retries):
                            try:
                                # Scrape (Returns a list of dicts and a flag)
                                scraped_info_list, is_empty_result = scrape_masothue(driver, buyer_name, crawl_details=crawl_details)
                                success = True
                                break # Success, exit retry loop
                            except Exception as e:
                                logger.warning(f"Attempt {attempt + 1}/{max_retries} failed for '{buyer_name}': {e}")
                                st.toast(f"Error scraping '{buyer_name}'. Retrying...", icon="⚠️")
                                
                                if attempt < max_retries - 1:
                                    # Retry
                                    human_delay(2, 4)
                                else:
                                    logger.error(f"All retries failed for '{buyer_name}'")
                                    st.error(f"Failed to scrape '{buyer_name}' after {max_retries} attempts.")
                        
                        if not success:
                            # User requested to STOP if scraping fails, so they can resume later.
                            # We do NOT save this row to the CSV.
                            # Next time they run, this company will be in the 'unprocessed' list.
                            logger.error(f"🛑 Stopping scraping due to repeated failures for: {buyer_name}")
                            st.error(f"🛑 Scraping stopped due to repeated failures for '{buyer_name}'.")
                            st.stop()
                        elif is_empty_result:
                            # User requested to skip if only specific navigation links are found
                            logger.info(f"⏭️ Skipping '{buyer_name}' - No actual results found.")
                            # We still need to update checkpoint so it's marked as processed
                            current_absolute_index = start_index + i
                            save_checkpoint(uploaded_file.name, current_absolute_index, buyer_name, total_rows)
                            human_delay(1, 2)
                            progress_bar.progress((i + 1) / total_rows)
                            continue
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
