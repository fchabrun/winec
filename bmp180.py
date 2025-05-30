"""
This program handles the communication over I2C between a Raspberry Pi and a
BMP180 Temperature/Pressure sensor.
Made by: MrTijn/Tijndagamer
Copyright 2015-2017
Released under the MIT license.
"""

import smbus
import math
from time import sleep


class bmp180:
    # Global variables
    address = None
    bus = None
    mode = 1  # TODO: Add a way to change the mode

    # BMP180 registers
    CONTROL_REG = 0xF4
    DATA_REG = 0xF6

    # Calibration data registers
    CAL_AC1_REG = 0xAA
    CAL_AC2_REG = 0xAC
    CAL_AC3_REG = 0xAE
    CAL_AC4_REG = 0xB0
    CAL_AC5_REG = 0xB2
    CAL_AC6_REG = 0xB4
    CAL_B1_REG = 0xB6
    CAL_B2_REG = 0xB8
    CAL_MB_REG = 0xBA
    CAL_MC_REG = 0xBC
    CAL_MD_REG = 0xBE

    # Calibration data variables
    calAC1 = 0
    calAC2 = 0
    calAC3 = 0
    calAC4 = 0
    calAC5 = 0
    calAC6 = 0
    calB1 = 0
    calB2 = 0
    calMB = 0
    calMC = 0
    calMD = 0


    def __init__(self, bus, address):
        self.bus = smbus.SMBus(bus)
        self.address = address

        # Get the calibration data from the BMP180
        self.read_calibration_data()

    # I2C methods

    def read_signed_16_bit(self, register):
        """Reads a signed 16-bit value.

        register -- the register to read from.
        Returns the read value.
        """
        msb = self.bus.read_byte_data(self.address, register)
        lsb = self.bus.read_byte_data(self.address, register + 1)

        if msb > 127:
            msb -= 256

        return (msb << 8) + lsb

    def read_unsigned_16_bit(self, register):
        """Reads an unsigned 16-bit value.

        Reads the given register and the following, and combines them as an
        unsigned 16-bit value.
        register -- the register to read from.
        Returns the read value.
        """
        msb = self.bus.read_byte_data(self.address, register)
        lsb = self.bus.read_byte_data(self.address, register + 1)

        return (msb << 8) + lsb

    # BMP180 interaction methods

    def read_calibration_data(self):
        """Reads and stores the raw calibration data."""
        self.calAC1 = self.read_signed_16_bit(self.CAL_AC1_REG)
        self.calAC2 = self.read_signed_16_bit(self.CAL_AC2_REG)
        self.calAC3 = self.read_signed_16_bit(self.CAL_AC3_REG)
        self.calAC4 = self.read_unsigned_16_bit(self.CAL_AC4_REG)
        self.calAC5 = self.read_unsigned_16_bit(self.CAL_AC5_REG)
        self.calAC6 = self.read_unsigned_16_bit(self.CAL_AC6_REG)
        self.calB1 = self.read_signed_16_bit(self.CAL_B1_REG)
        self.calB2 = self.read_signed_16_bit(self.CAL_B2_REG)
        self.calMB = self.read_signed_16_bit(self.CAL_MB_REG)
        self.calMC = self.read_signed_16_bit(self.CAL_MC_REG)
        self.calMD = self.read_signed_16_bit(self.CAL_MD_REG)

    def get_raw_temp(self):
        """Reads and returns the raw temperature data."""
        # Write 0x2E to CONTROL_REG to start the measurement
        self.bus.write_byte_data(self.address, self.CONTROL_REG, 0x2E)

        # Wait 4,5 ms
        sleep(0.0045)

        # Read the raw data from the DATA_REG, 0xF6
        raw_data = self.read_unsigned_16_bit(self.DATA_REG)

        # Return the raw data
        return raw_data

    def get_raw_pressure(self):
        """Reads and returns the raw pressure data."""
        # Write appropriate data to sensor to start the measurement
        self.bus.write_byte_data(self.address, self.CONTROL_REG, 0x34 + (self.mode << 6))

        # Sleep for 8 ms.
        # TODO: Way to use the correct wait time for the current mode
        sleep(0.008)

        MSB = self.bus.read_byte_data(self.address, self.DATA_REG)
        LSB = self.bus.read_byte_data(self.address, self.DATA_REG + 1)
        XLSB = self.bus.read_byte_data(self.address, self.DATA_REG + 2)

        raw_data = ((MSB << 16) + (LSB << 8) + XLSB) >> (8 - self.mode)

        return raw_data

    def get_temp(self):
        """Reads the raw temperature and calculates the actual temperature.

        The calculations used to get the actual temperature are from the BMP-180
        datasheet.
        Returns the actual temperature in degrees Celcius.
        """
        UT = self.get_raw_temp()

        X1 = 0
        X2 = 0
        B5 = 0
        actual_temp = 0.0

        X1 = ((UT - self.calAC6) * self.calAC5) / math.pow(2, 15)
        X2 = (self.calMC * math.pow(2, 11)) / (X1 + self.calMD)
        B5 = X1 + X2
        actual_temp = ((B5 + 8) / math.pow(2, 4)) / 10

        return actual_temp

    def get_pressure(self):
        """Reads and calculates the actual pressure.

        Returns the actual pressure in Pascal.
        """
        UP = self.get_raw_pressure()
        UT = self.get_raw_temp()
        B3 = 0
        B4 = 0
        B5 = 0
        B6 = 0
        B7 = 0
        X1 = 0
        X2 = 0
        X3 = 0
        pressure = 0

        # These calculations are from the BMP180 datasheet, page 15

        # Not sure if these calculations should be here, maybe they could be
        # removed?
        X1 = ((UT - self.calAC6) * self.calAC5) / math.pow(2, 15)
        X2 = (self.calMC * math.pow(2, 11)) / (X1 + self.calMD)
        B5 = X1 + X2

        # Todo: change math.pow cals to constants
        B6 = B5 - 4000
        X1 = (self.calB2 * (B6 * B6 / math.pow(2, 12))) / math.pow(2, 11)
        X2 = self.calAC2 * B6 / math.pow(2, 11)
        X3 = X1 + X2
        B3 = (((self.calAC1 * 4 + int(X3)) << self.mode) + 2) / 4
        X1 = self.calAC3 * B6 / math.pow(2, 13)
        X2 = (self.calB1 * (B6 * B6 / math.pow(2, 12))) / math.pow(2, 16)
        X3 = ((X1 + X2) + 2) / math.pow(2, 2)
        B4 = self.calAC4 * (X3 + 32768) / math.pow(2,15)
        B7 = (UP - B3) * (50000 >> self.mode)

        if B7 < 0x80000000:
            pressure = (B7 * 2) / B4
        else:
            pressure = (B7 / B4) * 2

        X1 = (pressure / math.pow(2, 8)) * (pressure / math.pow(2, 8))
        X1 = (X1 * 3038) / math.pow(2, 16)
        X2 = (-7357 * pressure) / math.pow(2, 16)
        pressure = pressure + (X1 + X2 + 3791) / math.pow(2, 4)

        return pressure

    def get_altitude(self, sea_level_pressure = 101325):
        """Calulates the altitude.

        This method calculates the altitude using the pressure.
        This method is not reliable when the sensor is inside.
        sea_level_pressure -- the pressure at the sea level closest to you in
        Pascal.
        Returns the altitude in meters.

        !!! This method probably does not work correctly. I've tried to test
        it but at the moment I have no way of verifying the data. !!!
        """
        altitude = 0.0
        pressure = float(self.get_pressure())

        altitude = 44330.0 * (1.0 - math.pow(pressure / sea_level_pressure, 0.00019029495))

        return altitude


if __name__ == "__main__":
    for bus, address in zip((1, 4), (0x77, 0x77)):
        print(f"reading sensor at {bus=} & {address=}")
        try:
            test_bmp = bmp180(bus, address=address)
            print(f"    temp: {test_bmp.get_temp()}")
            print(f"    pressure: {test_bmp.get_pressure()}")
            print(f"    altitude: {test_bmp.get_altitude()}")
        except Exception as error:
            print(f"    unable to read sensor, {error=}")

