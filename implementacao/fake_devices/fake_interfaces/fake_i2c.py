#!/usr/bin/env python3
#
# References:
#  Article "Using the I2C-Stub to Emulate a Device"
#   (https://eraretuya.github.io/2016/12/10/the-i2c-stub-in-action/)
#  smbus2 (https://github.com/kplindegaard/smbus2/)

import os
import subprocess
import smbus2

class FakeI2cException(Exception):
    """
    Base class for fake i2c bus related exceptions.
    """
    pass


class FakeI2cBus(smbus2.SMBus):
    """
    Fake I2C bus implementation.
    """
    def __init__(self, bus=None, devices_list=None):
        """
        Initialize and (optionally) open an i2c bus connection.
        """
        super().__init__()
        self.__bus = bus
        self.__real_bus = None
        self.__bus_link = None
        self.__real_bus_path = None
        self.__devices_list = None
        if bus is not None:
            self.open(bus, devices_list)

    def __del__(self):
        self.close()

    def __str__(self):
        return self.bus_path()

    def open(self, bus, devices_list):
        """
        Open a given i2c bus.
        """
        self.__bus = bus
        self.__devices_list = devices_list
        self.__add_fake_devices(devices_list)
        super().open(self.__real_bus)

    def close(self):
        """
        Close the i2c connection.
        """
        super().close()
        self.__del_fake_devices()

    def bus(self):
        """
        Get the number of the fake i2c bus (symlink).
        """
        return self.__bus

    def bus_path(self):
        """
        Get the path of the fake i2c bus (symlink).
        """
        if self.__bus_link:
            return self.__bus_link
        return ''

    def real_bus(self):
        """
        Get the number of the real i2c bus.
        """
        return self.__real_bus

    def real_bus_path(self):
        """
        Get the path of the real i2c bus (symlink).
        """
        if self.__real_bus_path:
            return self.__real_bus_path
        return ''

    def __add_fake_devices(self, devices_list):
        """
        Load i2c-stub with fake devices.
        """
        self.__run_cmd_raise_exception('modprobe i2c-dev')
        self.__run_cmd_raise_exception('modprobe -r i2c-stub')
        list_addr = ','.join(map(hex, devices_list))
        cmd = 'modprobe i2c-stub chip_addr=' + list_addr
        output = self.__run_cmd_raise_exception(cmd)
        self.__symlink_i2c_stub()

    def __del_fake_devices(self):
        """
        Unload i2c-stub.
        """
        try:
            self.__run_cmd('modprobe -r i2c-stub')
            os.unlink(self.__bus_link)
        except:
            # ignore errors
            pass

    def __run_cmd(self, cmd):
        """
        Run shell command.
        """
        result = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        return result.returncode, result.stdout.decode(), result.stderr.decode()

    def __run_cmd_raise_exception(self, cmd):
        """
        Run shell command and raise an exception when an error occurs.
        """
        result = self.__run_cmd(cmd)
        if result[0] != 0:
            raise FakeI2cException('Cannot run command \'{}\'. '\
                    'Shell returns: [{}] - {}'\
                    .format(cmd, result[0], result[2]))
        return result[0], result[1]

    def __symlink_i2c_stub(self):
        """
        Identify the bus i2c-stub and create a symlink.
        """
        output = self.__run_cmd_raise_exception('i2cdetect -l')
        i2c_bus = None
        for line in output[1].split('\n'):
            if 'SMBus stub driver' in line:
                i2c_bus = line.split()[0]
                self.__real_bus = int(i2c_bus.strip('i2c-'))
                break

        if i2c_bus is None:
            raise FakeI2cException('SMBus stub driver not found')

        self.__bus_link = '/dev/i2c-' + str(self.__bus)
        try:
            if (os.path.islink(self.__bus_link) and not
                    os.path.exists(os.readlink(self.__bus_link))):
                os.unlink(self.__bus_link)

            self.__real_bus_path = '/dev/' + i2c_bus

            if not os.path.islink(self.__bus_link):
                os.symlink(self.__real_bus_path, self.__bus_link)
        except Exception as e:
            raise FakeI2cException('Cannot create fake i2c symlink: ' + repr(e))
