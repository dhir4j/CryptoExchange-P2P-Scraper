# P2P Exchange Data Scraper

This repository contains a powerful P2P exchange scraper built using Python, Selenium, and gspread. It is designed to gather comprehensive P2P trading data across multiple cryptocurrency exchanges, currently supporting **Binance**, **OKX**, and **Bybit**. This scraper extracts key data points for each fiat currency listed on these exchanges, including:

- **Advertiser Name**: The name of the individual or entity listing the P2P ad.
- **Price**: The exchange rate or price per unit in the specified fiat currency.
- **Available Amount**: The amount of cryptocurrency available in each listing.
- **Payment Methods**: All accepted payment methods for each listing.
- **Payment Options**: Filtered list of payment methods based on user-defined bank criteria.
- **Amount Summary**: Consolidated summary of available amounts across payment methods.

In addition, the scraper includes:
- A **Bank Filter** feature to target specific bank payment methods.
- A **Dashboard** feature to provide real-time monitoring and analytics of scraped data.

## Table of Contents
1. [Features](#features)
2. [Installation](#installation)
3. [Usage](#usage)
4. [Configuration](#configuration)
5. [Output](#output)
6. [License](#license)

---

## Features

### 1. Multi-Exchange Scraping
The scraper supports three major exchanges:
- **Binance**
- **OKX**
- **Bybit**

Each exchange has its unique data structure and pagination that is handled by specific functions within the scraper, ensuring seamless data extraction.

### 2. Comprehensive Data Extraction
For each fiat currency on the exchanges, the scraper gathers:
- **Advertiser details** (name, order completion rate, etc.)
- **Price per unit** (in fiat currency)
- **Available amount** of cryptocurrency
- **List of payment methods** accepted for each listing

### 3. Bank Filter
With the **Bank Filter** feature, you can focus on listings that accept bank transfer methods, which is especially useful for tracking specific transaction types in the P2P market. This filter can be customized to include various bank names and exclude non-relevant payment options.

### 4. Dashboard
The **Dashboard** feature leverages Google Sheets as a real-time data visualization tool, displaying up-to-date information on liquidity, price trends, and available payment methods across all exchanges. Each scrape session updates the dashboard automatically, making it easy to monitor and analyze trends directly in Google Sheets.

## Installation

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/yourusername/p2p-exchange-scraper.git
   cd p2p-exchange-scraper
