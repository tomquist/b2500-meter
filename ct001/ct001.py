import socket
import threading
import time
from config.logger import logger


class CT001:
    def __init__(
        self,
        udp_port=12345,
        tcp_port=12345,
        dedupe_time_window=10,
        on_connect=None,
        on_disconnect=None,
        before_send=None,
        after_send=None,
        poll_interval=1
    ):
        self.dedupe_time_window = dedupe_time_window
        self.poll_interval = poll_interval
        self._udp_port = udp_port
        self._tcp_port = tcp_port
        self._last_response_time = {}
        self._on_connect = on_connect
        self._on_disconnect = on_disconnect
        self._before_send = before_send
        self._after_send = after_send
        self._value = [0, 0, 0]
        self._value_mutex = threading.Lock()
        self._udp_thread = None
        self._tcp_thread = None
        self._stop = False

    @property
    def on_connect(self):
        return self._on_connect

    @on_connect.setter
    def on_connect(self, callback):
        self._on_connect = callback

    @property
    def on_disconnect(self):
        return self._on_disconnect

    @on_disconnect.setter
    def on_disconnect(self, callback):
        self._on_disconnect = callback

    @property
    def before_send(self):
        return self._before_send

    @before_send.setter
    def before_send(self, callback):
        self._before_send = callback

    @property
    def after_send(self):
        return self._after_send

    @after_send.setter
    def after_send(self, callback):
        self._after_send = callback

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        with self._value_mutex:
            self._value = value

    def udp_server(self):
        udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_sock.bind(("", self._udp_port))
        logger.info("UDP server is listening...")

        try:
            while not self._stop:
                data, addr = udp_sock.recvfrom(1024)
                decoded = data.decode()
                current_time = time.time()

                logger.debug(f"Received '{decoded}' ({data.hex()}) from {addr}")
                if decoded == "hame":
                    if (
                        addr not in self._last_response_time
                        or (current_time - self._last_response_time[addr])
                        > self.dedupe_time_window
                    ):
                        logger.debug(f"Received 'hame' from {addr}")
                        udp_sock.sendto(b"ack", addr)

                        self._last_response_time[addr] = current_time
                        logger.debug(f"Received 'hame' from {addr}, sent 'ack'")
                    else:
                        logger.debug(
                            f"Received 'hame' from {addr} but ignored due to dedupe window"
                        )
                else:
                    logger.debug(f"Ignoring unknown message")

        finally:
            udp_sock.close()

    def handle_tcp_client(self, conn, addr):
        logger.info(f"TCP connection established with {addr}")
        try:
            data = conn.recv(1024)
            decoded = data.decode()
            if decoded == "hello":
                logger.debug("Received 'hello'")

                if self.on_connect:
                    self.on_connect(addr)

                last_send_time = 0
                while not self._stop:
                    current_time = time.time()
                    time_since_last_send = current_time - last_send_time

                    if time_since_last_send >= self.poll_interval:
                        if self.before_send:
                            self.before_send(addr)

                        with self._value_mutex:
                            if self.value is None:
                                logger.debug(f"No value to send to {addr}")
                                break
                            value1, value2, value3 = self.value

                        value1 = round(value1)
                        value2 = round(value2)
                        value3 = round(value3)

                        message = f"HM:{value1}|{value2}|{value3}"
                        try:
                            conn.send(message.encode())
                            last_send_time = current_time
                            logger.debug(f"Sent message to {addr}: {message}")
                            if self.after_send:
                                self.after_send(addr)

                            time.sleep(self.poll_interval)
                        except BrokenPipeError:
                            logger.warning(
                                f"Connection with {addr} broken. Waiting for a new connection."
                            )
                            break
                    else:
                        logger.debug(
                            f"Waiting for {self.poll_interval - time_since_last_send} seconds"
                        )
                        # Sleep a small amount to prevent busy waiting
                        time.sleep(0.01)
            else:
                logger.warning(f"Received unknown TCP message: {decoded}")
        finally:
            conn.close()
            logger.info(f"Connection with {addr} closed")
            if self.on_disconnect:
                self.on_disconnect(addr)

    def tcp_server(self):
        tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp_sock.bind(("", self._tcp_port))
        tcp_sock.listen(5)
        logger.info("TCP server is listening...")

        try:
            while not self._stop:
                conn, addr = tcp_sock.accept()
                client_thread = threading.Thread(
                    target=self.handle_tcp_client, args=(conn, addr)
                )
                client_thread.start()
        finally:
            logger.info("Stop listening for TCP connections")
            tcp_sock.close()

    def start(self):
        if self._udp_thread or self._tcp_thread:
            return
        self._stop = False
        self._udp_thread = threading.Thread(target=self.udp_server)
        self._tcp_thread = threading.Thread(target=self.tcp_server)

        self._udp_thread.start()
        self._tcp_thread.start()

    def join(self):
        if self._udp_thread:
            self._udp_thread.join()
        if self._tcp_thread:
            self._tcp_thread.join()

    def stop(self):
        self._stop = True
        if self._udp_thread:
            self._udp_thread.join()
        if self._tcp_thread:
            self._tcp_thread.join()
        self._udp_thread = None
        self._tcp_thread = None
