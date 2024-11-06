from datetime import datetime
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    ElementClickInterceptedException,
)
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import re
from google.oauth2.service_account import Credentials
import gspread
from OKX_unique_payment_methods import (
    process_payment_methods_for_fiat,
    update_single_fiat_payment_methods,
)

fiat_currencies = [
    "AED", "AMD", "ARS", "AUD", "AZN", "BGN", "BHD",
    "BRL", "BWP", "BYN", "CAD", "CHF", "CLP", "CNY", "COP", "CZK", "DKK", 
    "DOP", "EGP", "ETB", "EUR", "GBP", "GEL", "GHS", "HUF", "IDR", 
    "ILS", "INR", "IQD", "ISK", "JMD", "JOD", "JPY", "KES", "KGS", "KWD",
    "KZT", "LAK", "LBP", "LKR", "MAD", "MDL", "MOP",
    "MXN", "MZN", "NOK", "NPR", "NZD", "OMR", "PAB", "PEN", "PKR", 
    "PLN", "PYG", "QAR", "RON", "RSD", "RWF", "SAR", "SDG", "SEK", "THB", "TJS", "TND", 
    "TRY", "TTD", "TZS", "UAH", "UGX", "USD", "UYU", "UZS", "VES", "VND", "XAF", "XOF", 
    "ZAR", "ZMW"
]



def wait_for_page_to_load(driver, timeout=5):
    """Wait until the page content is fully loaded."""
    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.CLASS_NAME, "merchant-name"))
        )
        print("Page loaded successfully.")
    except TimeoutException:
        print("Timeout while waiting for the page to load.")

def click_element(driver, xpath):
    """Click an element using JavaScript if standard click fails."""
    try:
        element = driver.find_element(By.XPATH, xpath)
        driver.execute_script("arguments[0].click();", element)
    except NoSuchElementException as e:
        print(f"Error occurred while locating element: {e}")

def scrape_page(driver):
    """Scrape data from the current page on OKX."""
    advertisers = []
    prices = []
    available_amounts = []
    payment_methods = []

    rows = driver.find_elements(By.CSS_SELECTOR, "tr.custom-table-row")

    if not rows:
        print("No rows found on the page.")
        return advertisers, prices, available_amounts, payment_methods

    for row_index, row in enumerate(rows[1:], start=1):
        try:
            # Extract advertiser name
            advertiser_name_elem = row.find_element(
                By.CSS_SELECTOR, ".merchant-name a"
            )
            advertiser_name = advertiser_name_elem.text

            # Extract price
            price_elem = row.find_element(By.CSS_SELECTOR, ".price")
            price = re.sub(r"[^\d.]", "", price_elem.text).strip()
            price = float(price)

            # Extract available amount
            available_amount_elem = row.find_element(
                By.CSS_SELECTOR, ".quantity-and-limit .show-item:first-child"
            )
            available_amount = re.sub(r"[^\d.]", "", available_amount_elem.text).strip()
            available_amount = float(available_amount)

            # Extract payment methods
            payment_methods_elems = row.find_elements(
                By.CSS_SELECTOR, ".payment-item .pay-method"
            )
            payment_methods_list = [pm.text.strip() for pm in payment_methods_elems]
            payment_methods_str = ", ".join(payment_methods_list)

            # Append data to lists
            advertisers.append(advertiser_name)
            prices.append(price)
            available_amounts.append(available_amount)
            payment_methods.append(payment_methods_str)

            if advertisers and price and available_amount and payment_methods:
                print(
                    f"Advertiser: {advertiser_name}, Price: {price}, Available Amount: {available_amount} USDT, Payment Methods: {payment_methods_str}"
                )
        except Exception as e:
            print(f"Error occurred while processing row {row_index}: {e}")

    return advertisers, prices, available_amounts, payment_methods

def paginate_and_load_pages(driver):
    all_advertisers = []
    all_prices = []
    all_amounts = []
    all_payment_methods = []

    wait_for_page_to_load(driver)
    current_page_num = 1

    print(f"Scraping page {current_page_num} (first page)...")
    advertisers, prices, amounts, payment_methods = scrape_page(driver)
    all_advertisers.extend(advertisers)
    all_prices.extend(prices)
    all_amounts.extend(amounts)
    all_payment_methods.extend(payment_methods)

    while True:
        try:
            next_button = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "li.okui-pagination-next"))
            )

            # Check if the next button is disabled
            next_button_class = next_button.get_attribute("class")
            if "okui-pagination-disabled" in next_button_class:
                print("Next button is disabled. Reached the last page.")
                break

            # Add delay before moving to next page
            time.sleep(2)

            next_button.click()
            print(f"Clicked next page button. Now scraping page {current_page_num + 1}...")

            wait_for_page_to_load(driver)
            current_page_num += 1

            advertisers, prices, amounts, payment_methods = scrape_page(driver)
            all_advertisers.extend(advertisers)
            all_prices.extend(prices)
            all_amounts.extend(amounts)
            all_payment_methods.extend(payment_methods)

        except ElementClickInterceptedException:
            print("Next button is obscured. Trying to scroll...")
            driver.execute_script("arguments[0].scrollIntoView(true);", next_button)
            time.sleep(0.5)  # Delay after scrolling
            try:
                # Add delay before moving to next page
                time.sleep(5)

                driver.execute_script("arguments[0].click();", next_button)
                print(
                    f"Clicked next page button after scrolling. Now scraping page {current_page_num + 1}..."
                )

                wait_for_page_to_load(driver)
                current_page_num += 1

                advertisers, prices, amounts, payment_methods = scrape_page(driver)
                all_advertisers.extend(advertisers)
                all_prices.extend(prices)
                all_amounts.extend(amounts)
                all_payment_methods.extend(payment_methods)

            except Exception as e:
                print(f"Failed to click next button after scrolling: {e}")
                break

        except (NoSuchElementException, TimeoutException):
            print("No more pages or unable to click the next page button.")
            break

    return all_advertisers, all_prices, all_amounts, all_payment_methods

def main():
    # Configure Firefox options
    options = Options()
    options.headless = True  # Set to True to run the browser in headless mode

    # Set up the Firefox WebDriver
    service = Service("C:\\Program Files\\GeckoDriver\\geckodriver.exe")  # Path to your geckodriver
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

            url = f"https://www.okx.com/p2p-markets/{currency}/buy-usdt"
            driver.get(url)
            # Start scraping data from the page
            all_advertisers, all_prices, all_amounts, all_payment_methods = paginate_and_load_pages(driver)

            # Create a DataFrame from the lists
            df = pd.DataFrame(
                {
                    "Advertiser Name": all_advertisers,
                    "Price": all_prices,
                    "Available Amount": all_amounts,
                    "Payment Methods": all_payment_methods,
                }
            )

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

            # Call the sorting program after updating the sheet
            process_payment_methods_for_fiat(currency, workbook)

            # After updating a fiat worksheet, update the "Main" sheet
            update_single_fiat_payment_methods(currency, workbook)

            print(f"Data for {currency} has been scraped and updated successfully.\n")

        except Exception as e:
            print(f"An error occurred while processing currency {currency}: {e}")

    # Get current date and time and update column D for all rows from 2 to 63
    main_sheet = workbook.worksheet("Main")
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    main_sheet.update(range_name="D2:D80", values=[[current_time]] * 79)
    # Close the WebDriver
    driver.quit()

if __name__ == "__main__":
    main()
