from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
from selenium.common.exceptions import NoSuchElementException, TimeoutException, ElementClickInterceptedException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import time
from unique_payment_methods import process_payment_methods_for_fiat, update_single_fiat_payment_methods

# List of fiat currencies
fiat_currencies = [
    "AED", "AMD", "AOA", "ARS", "AUD", "AZN", "BDT", "BHD", "BIF", "BND",
    "BOB", "BRL", "BWP", "BYN", "CAD", "CDF", "CHF", "CLP", "CNY", "COP",
    "CRC", "CZK", "DOP", "DZD", "EGP", "ETB", "EUR", "GBP", "GEL", "GHS",
    "GMD", "GNF", "GTQ", "HKD", "HNL", "HUF", "IDR", "INR", "IQD", "JOD",
    "JPY", "KES", "KGS", "KHR", "KWD", "KZT", "LAK", "LBP", "LKR", "MAD",
    "MDL", "MGA", "MOP", "MRU", "MXN", "MZN", "NIO", "NOK", "NPR", "OMR",
    "PAB", "PEN", "PGK", "PHP", "PKR", "PLN", "PYG", "QAR", "RON", "RSD",
    "RWF", "SAR", "SDG", "SEK", "SLL", "THB", "TJS", "TND", "TRY", "TWD", 
    "TZS", "UAH", "UGX", "USD", "UYU", "UZS", "VES", "VND", "XAF", "XOF",
    "YER", "ZAR", "ZMW"
]

# ---- Data Retrieval ----
def scrape_page(driver):
    """Scrape data from the current page."""
    advertisers = []
    prices = []
    amounts = []
    payment_methods = []

    rows = driver.find_elements(By.CSS_SELECTOR, 'tr')

    if not rows:
        print("No rows found on the page.")
    
    for row in rows:
        try:
            # Use XPath to extract the advertiser name
            name_elem = row.find_element(By.CSS_SELECTOR, "a[href^='/advertiserDetail']")
            advertiser_name = name_elem.text

            # Extract price (convert to float)
            price_elem = row.find_element(By.CSS_SELECTOR, 'td:nth-child(2) .headline5')
            price = price_elem.text.replace(',', '')  # Remove any commas from numbers
            price = float(price)  # Convert string to float

            # Extract available amount (clean up "USDT" text and convert to float)
            amount_elem = row.find_element(By.CSS_SELECTOR, 'td:nth-child(3) .body3')
            available_amount = amount_elem.text.replace(' USDT', '').replace(',', '')  # Remove "USDT" and commas
            available_amount = float(available_amount)  # Convert string to float

            # Extract payment methods
            payment_methods_elems = row.find_elements(By.CSS_SELECTOR, 'td:nth-child(4) .PaymentMethodItem__text')
            payment_methods_list = [pm.text for pm in payment_methods_elems]
            payment_methods_str = ', '.join(payment_methods_list)

            # Append data to lists
            advertisers.append(advertiser_name)
            prices.append(price)
            amounts.append(available_amount)
            payment_methods.append(payment_methods_str)

        except NoSuchElementException:
            None
        except Exception as e:
            print(f"Error occurred while processing a row: {e}")

    return advertisers, prices, amounts, payment_methods

def paginate_and_load_pages(driver):
    """Handle pagination by clicking the next page button."""
    all_advertisers = []
    all_prices = []
    all_amounts = []
    all_payment_methods = []

    # Explicitly wait for the first page to fully load
    wait_for_page_to_load(driver)

    # Get the maximum page number from the pagination
    page_numbers = get_page_numbers(driver)
    max_pages = max(page_numbers) if page_numbers else 1
    print(f"Detected maximum page number: {max_pages}")

    # Scrape the first page
    current_page_num = 1
    print(f"Scraping page {current_page_num} (first page)...")
    advertisers, prices, amounts, payment_methods = scrape_page(driver)
    all_advertisers.extend(advertisers)
    all_prices.extend(prices)
    all_amounts.extend(amounts)
    all_payment_methods.extend(payment_methods)

    # Handle pagination by clicking the next button until no more pages or max page is reached
    while current_page_num < max_pages:
        # Close any potential overlays
        close_overlays(driver)

        # Locate and click the "Next Page" button
        try:
            print("Clicking next page...")
            next_button_xpath = "//div[@class='bn-pagination-next' and not(@aria-disabled='true')]"
            click_element(driver, next_button_xpath)

            # Explicitly wait for the page to load
            wait_for_page_to_load(driver)

            # Increment page number
            current_page_num += 1
            print(f"Scraping page {current_page_num}...")
            advertisers, prices, amounts, payment_methods = scrape_page(driver)
            all_advertisers.extend(advertisers)
            all_prices.extend(prices)
            all_amounts.extend(amounts)
            all_payment_methods.extend(payment_methods)

        except NoSuchElementException:
            print("No more pages to scrape. Stopping pagination.")
            break  # Break if the next page button is not found

    print(f"Stopped scraping after reaching max page limit of {max_pages} pages.")
    return all_advertisers, all_prices, all_amounts, all_payment_methods



def get_page_numbers(driver):
    """Retrieve the available page numbers from the pagination."""
    try:
        # Wait for the pagination items to be present
        page_elements = WebDriverWait(driver, 5).until(
            EC.presence_of_all_elements_located((By.XPATH, "//a[@class='bn-pagination-item' and not(contains(text(), '...'))]"))
        )
        # Extract the page numbers and convert them to integers
        return [int(elem.text) for elem in page_elements if elem.text.isdigit()]
    except TimeoutException:
        print("Timeout while waiting for pagination elements.")
        return []


def wait_for_page_to_load(driver, timeout=5):
    """Wait until the page content is fully loaded."""
    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "a[href^='/advertiserDetail']"))
        )
        print("Page loaded successfully.")
    except TimeoutException:
        print("Timeout while waiting for the page to load.")

def close_overlays(driver):
    """Close any overlays or pop-ups that may obstruct the pagination elements."""
    try:
        WebDriverWait(driver, 2).until(
            EC.element_to_be_clickable((By.XPATH, "//div[@id='onetrust-close-btn-container']"))
        ).click()
    except (TimeoutException, NoSuchElementException):
        # print("No overlay found or unable to close overlay.")
        None

def click_element(driver, xpath):
    """Click an element using JavaScript if standard click fails."""
    try:
        element = driver.find_element(By.XPATH, xpath)
        driver.execute_script("arguments[0].click();", element)
    except NoSuchElementException as e:
        print(f"Error occurred while locating element: {e}")

# ---- Main Function to Load and Scrape Pages ----
def main():
    # Configure Firefox options
    options = Options()
    options.headless = True # Set to True to run the browser in headless mode

    # Set up the Firefox WebDriver
    service = Service('C:\Program Files\GeckoDriver\geckodriver.exe')  # Path to your geckodriver
    driver = webdriver.Firefox(service=service, options=options)

    # Authenticate and initialize the Google Sheets client
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_file("credentials.json", scopes=scopes)
    client = gspread.authorize(creds)

    # Open the Google Sheets workbook by ID
    sheet_id = "insert google sheets api here"
    workbook = client.open_by_key(sheet_id)

    for currency in fiat_currencies:
        try:
            # Print the message before scraping
            print(f"Scraping {currency}...")

            # Construct the URL dynamically for each currency
            url = f'https://p2p.binance.com/en/trade/all-payments/USDT?fiat={currency}'
            driver.get(url)

            # Handle pagination and data extraction
            all_advertisers, all_prices, all_amounts, all_payment_methods = paginate_and_load_pages(driver)

            # Create a DataFrame from the lists
            df = pd.DataFrame({
                    'Advertiser Name': all_advertisers,
                    'Price': all_prices,
                    'Available Amount': all_amounts,
                    'Payment Methods': all_payment_methods,
            })

            # Create or access the corresponding worksheet for the currency
            try:
                worksheet = workbook.worksheet(currency)
                print(f"Updating existing worksheet for {currency}...")
            except gspread.WorksheetNotFound:
                worksheet = workbook.add_worksheet(title=currency, rows="1000", cols="10")
                print(f"Created new worksheet for {currency}...")

            # Clear existing data and update the worksheet with new data
            worksheet.clear()
            worksheet.update([df.columns.values.tolist()] + df.values.tolist())

            time.sleep(2)
            # Call the sorting program after updating the sheet
            process_payment_methods_for_fiat(currency)
            
            time.sleep(2)
            # After updating a fiat worksheet, update the "Main" sheet
            update_single_fiat_payment_methods(currency)

            print(f"Data for {currency} has been scraped and updated successfully.\n")

        except Exception as e:
            print(f"An error occurred while processing currency {currency}: {e}")

    # Get current date and time and update column C for all rows from 2 to 94
    main_sheet = workbook.worksheet('Main')
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    # main_sheet.update(f'C2:C94', [[current_time]] * 93)  # Updates C2 to C94
    main_sheet.update(range_name='D2:D94', values=[[current_time]] * 93)
    # Close the WebDriver
    driver.quit()

if __name__ == "__main__":
    main()