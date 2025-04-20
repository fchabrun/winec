import socket
import time

UDP_IP = "192.168.1.1"
UDP_PORT = 4210
MESSAGE = "13310000005"

sock = socket.socket(socket.AF_INET, # Internet
                     socket.SOCK_DGRAM) # UDP
while True:
    sock.sendto(MESSAGE, (UDP_IP, UDP_PORT))
    time.sleep(10);
