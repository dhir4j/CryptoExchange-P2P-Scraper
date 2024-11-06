from datetime import datetime
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
from selenium.common.exceptions import NoSuchElementException, TimeoutException, ElementClickInterceptedException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
from selenium.webdriver.common.action_chains import ActionChains
import re
from google.oauth2.service_account import Credentials
import gspread

# Import your custom modules
from BYBIT_unique_payment_methods import process_payment_methods_for_fiat, update_single_fiat_payment_methods

# List of fiat currencies to scrape
fiat_currencies = [
    "AED", "AMD", "ARS", "AUD", "AZN", "BDT", "BGN", "BRL",
    "BYN", "CAD", "CLP", "COP", "CZK", "DZD", "EGP", "EUR",
    "GBP", "GEL", "GHS", "HKD", "HUF", "IDR", "ILS", "INR",
    "JOD", "JPY", "KES", "KGS", "KHR", "KWD", "KZT", "LBP", "LKR",
    "MAD", "MDL", "MXN", "MYR", "NGN", "NOK", "NPR",
    "NZD", "PEN", "PHP", "PKR", "PLN", "RON", "RSD", "RUB", "SAR",
    "SEK", "THB", "TJS", "TRY", "TWD", "UAH", "USD", "UZS",
    "VES", "VND", "ZAR"
]

def clean_float_value(value):
    """Clean and validate float values before sending to Google Sheets."""
    if value is None:
        return 0.0
    try:
        float_val = float(value)
        if not (-1e308 <= float_val <= 1e308):  # Google Sheets float limit
            return 0.0
        return float_val
    except (ValueError, TypeError):
        return 0.0

def handle_warning_popup(driver):
    """Handle potential warning pop-up and click 'Confirm'."""
    try:
        confirm_button = WebDriverWait(driver, 2).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(@class, 'ant-btn-primary')]//span[text()='Confirm']"))
        )
        confirm_button.click()
        print("Warning pop-up handled successfully.")
    except (NoSuchElementException, TimeoutException):
        pass
    except Exception as e:
        print(f"An error occurred while handling the pop-up: {e}")

def close_warning_ad(driver):
    """Close the warning advertisement if present."""
    try:
        close_button = WebDriverWait(driver, 2).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, ".otc-ad-close"))
        )
        close_button.click()
        print("Warning advertisement closed successfully.")
    except (NoSuchElementException, TimeoutException):
        pass
    except Exception as e:
        print(f"An error occurred while closing the advertisement: {e}")

def wait_for_page_to_load(driver, timeout=5):
    """Wait until the page content is fully loaded."""
    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.CLASS_NAME, "advertiser-name"))
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
    """Scrape data from the current page on Bybit."""
    advertisers = []
    prices = []
    available_amounts = []
    payment_methods = []

    rows = driver.find_elements(By.CSS_SELECTOR, 'tr')

    if not rows:
        print("No rows found on the page.")
        return advertisers, prices, available_amounts, payment_methods
    
    for row_index, row in enumerate(rows[1:], start=1):
        try:
            # Extract advertiser name
            advertiser_name_elem = row.find_elements(By.CLASS_NAME, "advertiser-name")
            advertiser_name = advertiser_name_elem[0].text if advertiser_name_elem else 'N/A'

            # Enhanced price extraction to handle both formats
            try:
                # Try first format (price-amount class)
                price = 0.0
                price_amount_elem = row.find_elements(By.CLASS_NAME, "price-amount")
                if price_amount_elem:
                    price_text = price_amount_elem[0].text.split()[0]
                    price = clean_float_value(price_text)
                else:
                    # Try second format (text-[var(--bds-gray-t1-title)])
                    price_elem = row.find_element(By.CSS_SELECTOR, ".text-\\[var\\(--bds-gray-t1-title\\)\\]")
                    if price_elem:
                        # Extract the first number before the currency code
                        price_text = price_elem.text.strip().split()[0]
                        price = clean_float_value(price_text)

                if price == 0.0:  # If both attempts failed, try a more general approach
                    # Look for any element containing a price pattern
                    all_text_elements = row.find_elements(By.XPATH, ".//span[contains(@class, 'moly-text') or contains(@class, 'price-amount')]")
                    for elem in all_text_elements:
                        text = elem.text.strip()
                        # Use regex to find a number pattern
                        match = re.search(r'(\d+[.,]\d+)', text)
                        if match:
                            potential_price = clean_float_value(match.group(1))
                            if potential_price > 0:
                                price = potential_price
                                break

            except Exception as price_error:
                print(f"Debug - Price extraction error: {price_error}")
                price = 0.0

            # Extract available amount
            try:
                available_amount_elem = row.find_element(By.XPATH, ".//div[contains(@class, 'ql-value')][1]")
                amount_text = available_amount_elem.text
                amount_text = re.findall(r'[\d,.]+', amount_text)[0]
                available_amount = clean_float_value(amount_text.replace(',', ''))
            except:
                available_amount = 0.0

            # Extract payment methods
            payment_methods_elems = row.find_elements(By.CSS_SELECTOR, '.trade-list-tag')
            payment_methods_list = [pm.text for pm in payment_methods_elems]
            payment_methods_str = ', '.join(payment_methods_list) if payment_methods_list else 'N/A'

            # Only append valid data
            if advertiser_name != 'N/A' or price > 0 or available_amount > 0 or payment_methods_str != 'N/A':
                advertisers.append(advertiser_name)
                prices.append(price)
                available_amounts.append(available_amount)
                payment_methods.append(payment_methods_str)

                print(f"Row {row_index} - Advertiser: {advertiser_name}, "
                      f"Price: {price}, "
                      f"Available Amount: {available_amount} USDT, "
                      f"Payment Methods: {payment_methods_str}")
            else:
                print(f"Row {row_index} - No valid data found")

        except Exception as e:
            print(f"Error occurred while processing row {row_index}: {str(e)}")
            continue

    return advertisers, prices, available_amounts, payment_methods

def get_page_numbers(driver):
    """Retrieve the available page numbers from the pagination."""
    try:
        page_elements = WebDriverWait(driver, 5).until(
            EC.presence_of_all_elements_located((By.XPATH, "//div[@class='trade-table__pagination']//li[contains(@class, 'pagination-item')]"))
        )
        return [int(elem.text) for elem in page_elements if elem.text.isdigit()]
    except TimeoutException:
        print("Timeout while waiting for pagination elements.")
        return []

def paginate_and_load_pages(driver):
    """Navigate through all pages and collect data."""
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
        close_warning_ad(driver)
        handle_warning_popup(driver)

        try:
            next_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "li.pagination-next button[aria-label='next page']"))
            )
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
            time.sleep(0.5)
            try:
                driver.execute_script("arguments[0].click();", next_button)
                print(f"Clicked next page button after scrolling. Now scraping page {current_page_num + 1}...")

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

def update_worksheet_with_data(worksheet, df):
    """Update worksheet with proper formatting for numbers and strings."""
    try:
        # Clear existing content
        worksheet.clear()
        
        # Prepare headers
        headers = df.columns.tolist()
        worksheet.update('A1:D1', [headers])
        
        # Convert DataFrame to nested list format
        data_rows = []
        for _, row in df.iterrows():
            data_row = [
                str(row['Advertiser Name']),  # Keep as string
                float(row['Price']),          # Convert to float
                float(row['Available Amount']), # Convert to float
                str(row['Payment Methods'])    # Keep as string
            ]
            data_rows.append(data_row)
        
        # Update data if there are rows
        if data_rows:
            # Use batch_update with valueInputOption=RAW to prevent string conversion
            worksheet.spreadsheet.values_update(
                f'{worksheet.title}!A2:D{len(data_rows)+1}',
                params={'valueInputOption': 'RAW'},
                body={'values': data_rows}
            )
            
            # Set number formatting for price and amount columns
            worksheet.format(f'B2:C{len(data_rows)+1}', {
                "numberFormat": {
                    "type": "NUMBER",
                    "pattern": "#,##0.00"
                }
            })
        
        print("Worksheet updated successfully with proper formatting")
    except Exception as e:
        print(f"Error updating worksheet: {e}")    
        
def main():
    # Configure Firefox options
    options = Options()
    options.headless = True

    # Set up the Firefox WebDriver
    service = Service('C:\\Program Files\\GeckoDriver\\geckodriver.exe')
    driver = webdriver.Firefox(service=service, options=options)

    # Authenticate and initialize Google Sheets client
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_file("credentials.json", scopes=scopes)
    client = gspread.authorize(creds)

    # Open the Google Sheets workbook
    sheet_id = "insert google sheets api here"
    workbook = client.open_by_key(sheet_id)

    for currency in fiat_currencies:
        try:
            print(f"Scraping {currency}...")
            url = f'https://www.bybit.com/fiat/trade/otc?actionType=1&token=USDT&fiat={currency}&paymentMethod='
            driver.get(url)
            handle_warning_popup(driver)
            close_warning_ad(driver)

            all_advertisers, all_prices, all_amounts, all_payment_methods = paginate_and_load_pages(driver)

            # Clean the data before creating DataFrame
            cleaned_prices = [clean_float_value(price) for price in all_prices]
            cleaned_amounts = [clean_float_value(amount) for amount in all_amounts]

            df = pd.DataFrame({
                'Advertiser Name': all_advertisers,
                'Price': cleaned_prices,
                'Available Amount': cleaned_amounts,
                'Payment Methods': all_payment_methods,
            })

            try:
                worksheet = workbook.worksheet(currency)
                print(f"Updating existing worksheet for {currency}...")
            except gspread.WorksheetNotFound:
                worksheet = workbook.add_worksheet(title=currency, rows="1000", cols="10")
                print(f"Created new worksheet for {currency}...")

            # Convert DataFrame to list of lists and handle JSON compliance
            # Use the new update method
            update_worksheet_with_data(worksheet, df)

            # Process payment methods
            process_payment_methods_for_fiat(currency, workbook)
            update_single_fiat_payment_methods(currency, workbook)

            print(f"Data for {currency} has been scraped and updated successfully.\n")
            time.sleep(2)

        except Exception as e:
            print(f"An error occurred while processing currency {currency}: {e}")
            continue

    # Update timestamp
    try:
        main_sheet = workbook.worksheet('Main')
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        main_sheet.update(range_name='D2:D61', values=[[current_time]] * 60)
    except Exception as e:
        print(f"Error updating timestamp: {e}")

    driver.quit()

if __name__ == "__main__":
    main()