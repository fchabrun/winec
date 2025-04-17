MOSI_PIN = 10
SCK_PIN = 11
CS_PIN = 7

import time

from luma.led_matrix.device import max7219
from luma.core.interface.serial import spi, noop
from luma.core.virtual import sevensegment


def main():
    # create seven segment device
    serial = spi(port=0, device=0, gpio=noop())
    device = max7219(serial, cascaded=1)
    seg = sevensegment(device)

    while True:
        seg.text = "HLO"
        time.sleep(0.6)
        seg.text = "BYE"
        time.sleep(0.6)


if __name__ == '__main__':
    main()
