#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import logging
import os
import sys

class KingdomStoryCouponRedemption:
    def __init__(self, coupon_code):
        logging.basicConfig(
            level=logging.INFO, 
            format='%(asctime)s - %(levelname)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        self.logger = logging.getLogger(__name__)
        self.NEW_CODE = coupon_code
        
        # Chrome options for GitHub Actions
        options = Options()
        options.add_argument("--headless")  # Run headless in CI
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        
        self.browser = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()), 
            options=options
        )
        
        # Your server configurations here...
        self.SERVERS = {
            'US': {
                'server_name': 'Conquest (US)',
                'ids': [
                    "一蓑煙雨任平生", "龍之旗", "時光一如继往"
                ]
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
                'ids': ["kpop1", "丨MoonLight丨"]
            },
            'SEA': {
                'server_name': 'Warlord (SEA)',
                'ids': ["shushu1", "丨MoonLight丨"]
            },
            'JP': {
                'server_name': 'Invincible (JP)',
                'ids': [
                    "IkkiTousen", "陳羅森", "ZII5566", 
                    "有夢想的咸魚", "李麥特", "天意", "丨MoonLight丨"
                ]
            }
        }
    
    def _redeem_coupon(self, server_data, monarch_id):
        try:
            select_server = WebDriverWait(self.browser, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "span[class='js-selected-text']"))
            )
            select_server.click()

            server_xpath = f"//ul[@data-type='server']/li[text()='{server_data['server_name']}']"
            self.browser.find_element(By.XPATH, server_xpath).click()

            input_id = self.browser.find_element(By.NAME, "monarch")
            input_id.clear()
            input_id.send_keys(monarch_id)

            input_code = self.browser.find_element(By.NAME, "serialcode")
            input_code.clear()
            input_code.send_keys(self.NEW_CODE)

            submit = self.browser.find_element(By.XPATH, "/html/body/main/form/button")
            submit.click()

            time.sleep(1)
            message = WebDriverWait(self.browser, 10).until(
                EC.presence_of_element_located((By.XPATH, "/html/body/div[2]/div/p"))
            ).text
            
            self.logger.info(f"{monarch_id}: {message} - {self.NEW_CODE}")

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
                if not server_data['ids']:
                    self.logger.info(f"No IDs configured for {server}. Skipping.")
                    continue
                    
                self.logger.info(f"Redeeming on {server} server")
                
                for monarch_id in server_data['ids']:
                    self._redeem_coupon(server_data, monarch_id)

        except Exception as e:
            self.logger.error(f"Redemption failed: {e}")
        finally:
            self.browser.quit()

def main():
    # Get coupon code from command line argument or environment variable
    coupon_code = sys.argv[1] if len(sys.argv) > 1 else os.getenv('COUPON_CODE', 'kingdom')
    
    print(f"Running coupon redemption with code: {coupon_code}")
    coupon_redeemer = KingdomStoryCouponRedemption(coupon_code)
    coupon_redeemer.run_redemption()

if __name__ == "__main__":
    main()
