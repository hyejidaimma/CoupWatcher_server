import threading
import socket
import time
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
import pandas as pd

# 인터페이스 정의
class DataCrawler:
    def crawl(self):
        pass

class PriceNotifier:
    def notify(self, product_name, price):
        pass

class Server:
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=10)
        self.running = True
        self.data_list = []

    def handle_client(self, client_socket, address):
        while self.running:
            data = client_socket.recv(1024).decode()
            if not data:
                break

            # 'zgq'를 수신한 경우
            if data == 'zgq':
                self.show_current_price(client_socket)
            else:
                # 'zgq'가 아닌 다른 데이터인 경우, 데이터를 파싱하여 처리하기 위해 서브 스레드 생성
                threading.Thread(target=self.process_data, args=(data, client_socket)).start()

        # 클라이언트와의 연결 종료 후 정리
        client_socket.close()

    def process_data(self, data, client_socket):
        # 데이터 파싱하여 상품명, 구매희망가격, 상품링크를 추출
        product_name, desired_price, product_link = data.split(',')

        # 스레드 풀을 사용하여 작업 처리
        data_crawler = ItemDataCrawler(product_name, desired_price, product_link)
        price_notifier = PriceNotifierImpl(client_socket, self.data_list)
        data_crawler.crawl(price_notifier)

    def start(self):
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind(('localhost', 12345))
        server_socket.listen(5)
        print("Server listening on port 12345")

        while self.running:
            client_socket, address = server_socket.accept()
            print(f"Accepted connection from {address}")
            threading.Thread(target=self.handle_client, args=(client_socket, address)).start()

    def stop(self):
        self.running = False

    def show_current_price(self, client_socket):
        # 서브스레드가 생성되자마자 데이터 크롤링하여 클라이언트에게 송신
        data_crawler = ItemDataCrawler("", "", "")  # 빈 값으로 초기화하여 show_current_price 용도로 사용
        price_notifier = PriceNotifierImpl(client_socket, self.data_list)
        data_crawler.crawl(price_notifier)

class ItemDataCrawler(DataCrawler):
    def __init__(self, product_name, desired_price, product_link):
        self.product_name = product_name
        self.desired_price = int(desired_price)
        self.product_link = product_link

    def crawl(self, price_notifier):
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
                crawled_price = int(price_element.get_text(strip=True).replace(",", "").replace("원", ""))
                price_notifier.notify(self.product_name, crawled_price)

        except Exception as e:
            print(f"Exception occurred during crawling: {e}")

class PriceNotifierImpl(PriceNotifier):
    def __init__(self, client_socket, data_list):
        self.client_socket = client_socket
        self.data_list = data_list

    def notify(self, product_name, price):
        # 가격 정보를 클라이언트에 전송
        current_time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        print(f"Price at {current_time_str} for {product_name}: {price}원")
        self.client_socket.send(f"{product_name}/{current_time_str}/{price}".encode())

        # 데이터를 data_list에 추가하여 엑셀 파일에 저장
        data = {'Product Name': product_name, 'Price': price, 'Time': current_time_str}
        self.data_list.append(data)
        self.save_to_excel()

    def save_to_excel(self):
        df = pd.DataFrame(self.data_list)
        df.to_excel('crawl_data.xlsx', index=False)

if __name__ == "__main__":
    server = Server()
    try:
        server.start()
    except KeyboardInterrupt:
        server.stop()
