import os
import time


class ds18b20:
    def __init__(self, address, rootdir='/sys/bus/w1/devices/'):
        self.address = address
        self.rootdir = rootdir


    def read_temp_raw(self):
        device_filepath = os.path.join(self.rootdir, "28-" + self.address, "w1_slave")
        try:
            with open(device_filepath, 'r') as f:
                lines = f.readlines()
            return lines
        except:
            raise Exception("Unable to load w1 device file: not connected?")


    def read_temp(self):
        # read device file
        lines = self.read_temp_raw()
        # check something was read
        assert lines is not None, "Unable to read device file"
        assert len(lines) > 0, "Device file is empty"
        # check file was read and says status is OK
        assert lines[0].strip()[-3:] == 'YES', "Device file was read but status != YES"
        # read temperature from buffer
        equals_pos = lines[1].find('t=')
        assert equals_pos != -1, "Incorrect device file formatting"
        temp_string = lines[1][equals_pos + 2:]
        temp_c = float(temp_string) / 1000.0
        return temp_c


if __name__ == "__main__":
    addr1 = "000000bb35e7"
    addr2 = "000000bc51c5"

    for address in (addr1, addr2):
        # read temps
        print(f"reading temp_c at {address=}")
        ext_tmp = ds18b20(address=address)
        try:
            tstart = time.time()
            temp_c = ext_tmp.read_temp()
            tdur = time.time() - tstart
            print(f"    {temp_c=} acquired in {tdur:.1f} seconds")
        except Exception as error:
            print(f"    unable to read, {error=}")
