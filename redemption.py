#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define Chrome binary path
chrome_path = os.getenv("GOOGLE_CHROME_BIN", "/usr/bin/google-chrome")
if not os.path.exists(chrome_path):
    raise Exception(f"Could not find Chrome binary at {chrome_path}")

# Configure Chrome options
chrome_options = Options()
chrome_options.binary_location = chrome_path
chrome_options.add_argument("--headless")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")

class KingdomStoryCouponRedemption:
    def __init__(self, coupon_code):
        self.logger = logging.getLogger(__name__)
        self.NEW_CODE = coupon_code  # now using the argument

        # Initialize webdriver
        self.browser = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=chrome_options
        )

        # Servers configuration
        self.SERVERS = {
            'US': {
                'server_name': 'Conquest (US)',
                'ids': ["一蓑煙雨任平生", "龍之旗", "時光一如继往"]
            },
            'TW': {
                'server_name': 'Inferno (TW)',
                'ids': ["weibaibai", "魔动王风暴使者"]
            },
            'KOR8': {
                'server_name': 'Blue Sky (KOR)',
                'ids': ["初始886", "ffecg", "我過去總是祖", "吳若權限期",
                        "鱷魚邪惡", "甲魚躍升為", "午餐戶外課", "daG8", "魔動王地獄使者"]
            },
            'KOR': {
                'server_name': 'Orchard (KOR)',
                'ids': ["kpop1", "| MoonLight |"]
            },
            'SEA': {
                'server_name': 'Warlord (SEA)',
                'ids': ["shushu1", "| MoonLight |"]
            },
            'JP': {
                'server_name': 'Invincible (JP)',
                'ids': ["IkkiTousen", "陳羅森", "ZII5566", "有夢想的咸魚", "李麥特", "天意", "| MoonLight |"]
            }
        }

    def _redeem_coupon(self, server_data, monarch_id):
        try:
            # Wait for server selection dropdown
            select_server = WebDriverWait(self.browser, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "span[class='js-selected-text']"))
            )
            select_server.click()

            # Select specific server
            server_xpath = f"//ul[@data-type='server']/li[text()='{server_data['server_name']}']"
            self.browser.find_element(By.XPATH, server_xpath).click()

            # Input monarch ID
            input_id = self.browser.find_element(By.NAME, "monarch")
            input_id.clear()
            input_id.send_keys(monarch_id)

            # Input coupon code
            input_code = self.browser.find_element(By.NAME, "serialcode")
            input_code.clear()
            input_code.send_keys(self.NEW_CODE)

            # Submit
            submit = self.browser.find_element(By.XPATH, "/html/body/main/form/button")
            submit.click()

            # Wait and read confirmation
            time.sleep(1)
            message = WebDriverWait(self.browser, 10).until(
                EC.presence_of_element_located((By.XPATH, "/html/body/div[2]/div/p"))
            ).text

            self.logger.info(f"{monarch_id}: {message} - {self.NEW_CODE}")

            # Close confirmation
            close_button = self.browser.find_element(By.XPATH, "/html/body/div[2]/div/button")
            close_button.click()
            time.sleep(1)

        except Exception as e:
            self.logger.error(f"Error redeeming for {monarch_id}: {e}")

    def run_redemption(self, servers=None):
        try:
            self.browser.get("https://coupon.kingdom-story.com")

            if servers is None:
                servers = list(self.SERVERS.keys())

            for server in servers:
                if server not in self.SERVERS:
                    self.logger.warning(f"Server {server} not found. Skipping.")
                    continue

                server_data = self.SERVERS[server]
                self.logger.info(f"Redeeming on {server} server")

                for monarch_id in server_data['ids']:
                    self._redeem_coupon(server_data, monarch_id)

        except Exception as e:
            self.logger.error(f"Redemption failed: {e}")
        finally:
            self.browser.quit()

def main():
    coupon_redeemer = KingdomStoryCouponRedemption("gift4u")
    coupon_redeemer.run_redemption()
    # coupon_redeemer.run_redemption(['KOR8'])

if __name__ == "__main__":
    main()
