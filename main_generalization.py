import threading
import socket
import time
import requests
import schedule as schedule
from bs4 import BeautifulSoup
import openpyxl
from concurrent.futures import ThreadPoolExecutor

# 엑셀 파일에 대한 정보를 전역 변수로 선언(일반화)
EXCEL_FILE = "price_data.xlsx"
SHEET_NAME = "PriceData"

class ItemThread(threading.Thread):
    def __init__(self, client_socket, product_name, desired_price, product_link, daily_average_time):
        super(ItemThread, self).__init__()
        self.client_socket = client_socket
        self.product_name = product_name
        self.desired_price = desired_price
        self.product_link = product_link
        self.daily_average_time = daily_average_time
        self.running = True
        self.crawled_price = None
        self.crawled_count = 0
        self.average_price = 0
        self.hourly_prices = []

    def crawlingTest(self):
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36",
                "Accept-Language": "ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3"
            }

            res = requests.get(self.product_link, headers=headers)
            res.raise_for_status()

            soup = BeautifulSoup(res.text, "html.parser")

            # 가격 정보를 추출
            price_element = soup.select_one(".total-price")

            if price_element:
                # 문자열을 정수로 변환
                self.crawled_price = int(price_element.get_text(strip=True).replace(",", "").replace("원", ""))
                # (파이썬)클라이언트 전송 테스트용
                self.client_socket.send(str(self.crawled_price).encode())
                return self.crawled_price
            else:
                return 0
        except Exception as e:
            print(f"Exception occurred during crawling: {e}")
            return 0

    def calculate_daily_average(self):
        total_price = sum(self.hourly_prices)
        num_of_data_points = len(self.hourly_prices)

        if num_of_data_points == 0:
            print("No data points found for the day.")
            return

        # Daily average calculation
        daily_average = total_price / num_of_data_points
        print(f"Daily Average Price: {daily_average}")

        # Clear the list for the next day
        self.hourly_prices.clear()

    def save_to_excel(self, price_data):
        workbook = openpyxl.load_workbook(EXCEL_FILE)
        sheet = workbook[SHEET_NAME]
        sheet.append(price_data)
        workbook.save(EXCEL_FILE)
        workbook.close()

    def showCurrentPrice(self):
        self.crawlingTest()
        print(f"Current price: {self.crawled_price}")
        self.client_socket.send(str(self.crawled_price).encode())

    def killThread(self):
        self.running = False
        self.crawled_price = None
        self.crawled_count = 0

    def run(self):
        # 00:00부터 23:00까지 매 시 정각마다 크롤링을 수행하고 가격을 hourly_prices에 저장
        for hour in range(24):
            time_str = f"{hour:02d}:00"
            schedule.every().day.at(time_str).do(self.crawlingTest).tag(time_str)  # Add tag for each job

        # 매일 23:59에 calculate_daily_average() 함수를 실행하여 일평균 가격을 계산
        schedule.every().day.at(self.daily_average_time).do(self.calculate_daily_average)

class PriceServer:
    def __init__(self):
        try:
            workbook = openpyxl.load_workbook(EXCEL_FILE)
            workbook.close()
        except FileNotFoundError:
            workbook = openpyxl.Workbook()
            workbook.save(EXCEL_FILE)
            workbook.close()

        # 서버 설정
        self.server_host = 'localhost'
        self.server_port = 12345
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.server_host, self.server_port))
        self.server_socket.listen(5)
        print(f"Server listening on {self.server_host}:{self.server_port}")

        # 아이템별 일평균 계산 시간 설정
        self.item_daily_average_time = "23:59"  # 매일 23:59에 일평균 계산

        # 스레드풀 생성 (최대 10개의 스레드)
        self.thread_pool = ThreadPoolExecutor(max_workers=10)

    def handle_client(self, client_socket, address):
        while True:
            data = client_socket.recv(1024).decode()
            if not data:
                break
    
            product_name, desired_price, product_link = data.split(',')
            item_thread = ItemThread(client_socket, product_name, desired_price, product_link)
            item_thread.start()
    
        client_socket.close()

    def start(self):
        while True:
            client_socket, address = self.server_socket.accept()
            print(f"Accepted connection from {address}")

            data = client_socket.recv(1024).decode()
            if not data:
                client_socket.close()
                continue

            product_name, desired_price, product_link = data.split(',')
            item_thread = ItemThread(client_socket, product_name, desired_price, product_link, self.item_daily_average_time)
            # 스레드풀에 스레드 추가 및 실행
            self.thread_pool.submit(item_thread.start)

if __name__ == "__main__":
    price_server = PriceServer()
    price_server.start()
