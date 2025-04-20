import socket
import time

UDP_IP = "192.168.1.20"
UDP_PORT = 4210

sock = socket.socket(socket.AF_INET, # Internet
                     socket.SOCK_DGRAM) # UDP
cur_temp = 9.0
while True:
    MESSAGE = f"{int(round(cur_temp*10)):03}10000"
    assert len(MESSAGE) == 8, f"message is too long: {MESSAGE=}"
    sock.sendto(bytes(MESSAGE, "utf-8"), (UDP_IP, UDP_PORT))
    cur_temp += .1;
    time.sleep(5);
