import os
import time

default_w1_rootdir = '/sys/bus/w1/devices/'


def read_temp_raw(ds18b20_addr, w1_rootdir):
    device_filepath = os.path.join(w1_rootdir, "28-" + ds18b20_addr, "w1_slave")
    try:
        with open(device_filepath, 'r') as f:
            lines = f.readlines()
        return lines
    except:
        raise Exception("Unable to load w1 device file: not connected?")


def read_temp(ds18b20_addr, w1_rootdir, timeout=1.):
    tstart = time.time()
    while True:
        # handle timeout
        if time.time() - tstart > timeout:
            raise Exception("Timeout")
        # read device file
        lines = read_temp_raw(ds18b20_addr=ds18b20_addr, w1_rootdir=w1_rootdir)
        # break out of loop if file was read and is OK
        if lines[0].strip()[-3:] == 'YES':
            break
        # else, wait a little bit and start again until timeout
        time.sleep(0.1)
    assert lines is not None, "Unable to read device file"
    assert len(lines) > 0, "Device file is empty"

    equals_pos = lines[1].find('t=')
    if equals_pos != -1:
        temp_string = lines[1][equals_pos + 2:]
        temp_c = float(temp_string) / 1000.0
        return temp_c
    raise Exception("Incorrect device file formatting")


if __name__ == "__main__":
    addr1 = "000000bb35e7"
    addr2 = "000000bc51c5"

    while True:
        # read temps
        try:
            tstart = time.time()
            temp_c1 = read_temp(ds18b20_addr=addr1, w1_rootdir=default_w1_rootdir, timeout=.1)
            tdur = time.time() - tstart
            print(f"{temp_c1=} acquired in {tdur:.1f} seconds")
        except Exception as error:
            print(f"Unable to read temp_c1: {error=}")
        try:
            tstart = time.time()
            temp_c2 = read_temp(ds18b20_addr=addr2, w1_rootdir=default_w1_rootdir, timeout=1)
            tdur = time.time() - tstart
            print(f"{temp_c2=} acquired in {tdur:.1f} seconds")
        except Exception as error:
            print(f"Unable to read temp_c2: {error=}")
        # print
        # wait until next read
        time.sleep(2)
