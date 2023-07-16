import threading
import socket
import time
import requests
from bs4 import BeautifulSoup


class ItemThread(threading.Thread):
    def __init__(self, client_socket, product_name, desired_price, product_link):
        super(ItemThread, self).__init__()
        self.client_socket = client_socket
        self.product_name = product_name
        self.desired_price = desired_price
        self.product_link = product_link
        self.running = True
        self.crawled_price = None
        self.crawled_count = 0
        self.average_price = 0

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
                self.client_socket.send(price_element.encode())

                #self.crawled_price = price_element.get_text(strip=True)
                return True
            else:
                return False
        except Exception as e:
            print(f"Exception occurred during crawling: {e}")
            return False

    def crawlingOnTime(self):
        sum_price = 0
        while self.running:
            if self.crawlingTest():
                # 현재 시간 받아옴
                current_time = time.localtime()
                current_time_str = time.strftime("%Y-%m-%d %H:%M:%S", current_time)

                # 정각일 때만 가격을 기록
                if current_time.tm_min != 0 or current_time.tm_sec != 0:
                    continue
                time.sleep(1) # 중복 방지

                # 정각에 맞춰 주기적으로 크롤링하여 가격 정보를 클라이언트에 전송
                if self.crawled_price:
                    # 가격을 정수로 변환하여 클라이언트에게 송신
                    print(f"Price at {current_time_str}: {self.crawled_price}원")
                    sum_price += self.crawled_price

                self.crawled_count += 1
                if self.crawled_count % 24 == 0:
                    self.average_price = int(sum_price/24)

                    # 그래프를 작성하기 위한 날짜,가격 정보 송신
                    #data = current_time_str + '/' + str(self.average_price)
                    data = f'{current_time.tm_mon}/{current_time.tm_mday}' + '/' + str(self.average_price)
                    self.client_socket.send(data.encode())
                    self.crawled_count = 0
                    self.average_price = 0
                    sum_price = 0

    def showCurrentPrice(self):
        self.crawlingTest()
        print(f"Current price: {self.crawled_price}")
        self.client_socket.send(str(self.crawled_price).encode())

    def killThread(self):
        self.running = False
        self.crawled_price = None
        self.crawled_count = 0

    def run(self):
        self.crawlingOnTime()
        #self.showCurrentPrice()


def handle_client(client_socket, address):
    while True:
        data = client_socket.recv(1024).decode()
        if not data:
            break

        # 데이터 수신 후 '/'를 기준으로 분류하여 상품명, 구매희망가격, 상품링크를 추출
        product_name, desired_price, product_link = data.split(',')

        # 서브스레드 생성하여 ItemThread 클래스 실행
        item_thread = ItemThread(client_socket, product_name, desired_price, product_link)
        item_thread.start()

    client_socket.close()


def main():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(('localhost', 12345))
    server_socket.listen(5)
    print("Server listening on port 12345")

    while True:
        client_socket, address = server_socket.accept()
        print(f"Accepted connection from {address}")
        threading.Thread(target=handle_client, args=(client_socket, address)).start()


if __name__ == "__main__":
    main()
