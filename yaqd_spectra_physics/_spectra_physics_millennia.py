__all__ = ["SpectraPhysicsMillennia"]

import asyncio
import regex as re
import serial
from yaqd_core import UsesUart, aserial


query_re = re.compile(r"\?[A-Z,a-z,0-9,%]+\r")

int_re = re.compile(r"\d+")
current_re = re.compile(r"\d+.\d+A[12]")
percent_re = re.compile(r"[\d]+.[\d]+%")
power_re = re.compile(r"\d+.\d+W")

# TODO: HasPosition, HasLimits for power control
# TODO: IsSensor: use channels for monitoring power, currents

class SpectraPhysicsMillennia(UsesUart):
    _kind = "spectra-physics-millennia"

    def __init__(self, name, config, config_filepath):
        super().__init__(name, config, config_filepath)
        self._ser = aserial.ASerial(
            config["serial_port"], 
            baudrate=config["baud_rate"],
            eol=b"\n",
            xonxoff=True
        )
        # ddk: cannot get aserial commands to work; restricting to synchronous for now.
        self._ser.timeout = 0.1
        info = self.query("?IDN\r".encode())
        # manufacturer, product, sw_version, sn = info.split(",")
        self.logger.info(f"info {info}")

    async def update_state(self):
        """simple repeating update state. No _busy dependence.
        """
        state_keys = ["set_power", "power", "c1", "c2", "error_code"]
        while True:
            previous = {k: self._state[k] for k in state_keys}
            new = {}

            for key, command in zip(
                state_keys,
                ["?PSET", "?P", "?C1", "?C2", "?EC"],
            ):
                if command.startswith("?P"):
                    pattern = power_re
                elif command.startswith("?C"):
                    pattern = current_re
                else:
                    pattern = int_re
                while True: # retry at ~2Hz for failed requests 
                    newval, alarm = await self._write(command)
                    self.logger.debug(f"{newval}, {alarm}")
                    if alarm:
                        self.logger.debug(f"update {key} failed with {alarm}--retrying")
                        await asyncio.sleep(0.5)
                        continue
                    try:
                        match = pattern.match(newval)
                        new[key] = match[0]
                    except (ValueError, TypeError) as e:
                        self.logger.debug(f"looked for pattern {pattern} in {newval}")
                        self.logger.error(e)
                        await asyncio.sleep(0.5)
                        continue
                    self._state[key] = match[0]
                    break
            changed = {k : [previous[k], new[k]] for k in previous if previous[k] != new[k]}
            if changed:
                for k, v in changed.items():
                    self.logger.info(f"{k}: {v[0]} -> {v[1]}")
            else:
                for k in new.keys():
                    self.logger.debug(f"{k}: {previous[k]} -> {new[k]}")
            await asyncio.sleep(self._config["refresh_wait"])

    def direct_serial_write(self, message:bytes) -> str:
        self._ser.write(message)
        response = self._ser.read_until()
        self.logger.info(response)
        self.logger.info("leave dsw")
        return response.decode().rstrip("\\n")

    def query(self, message:bytes) -> str:
        """
        synchronous message yields response.
        regex restricts requests to "safe" operations (questions).
        e.g. you cannot change from current/power mode with this function
        for full control, use direct_serial_write
        Parameters
        ----------
        message : bytes
            Serial message. Include EOL.
        """
        # screen for queries
        match = query_re.fullmatch(message.decode())
        if match is None:
            raise ValueError(f"{message} is not a query")
        return self.direct_serial_write(message)

    async def _write(self, command:str):
        """asynchronous communication.  Follows command with check for error (?STB)
        """
        try:
            await asyncio.sleep(0.1)
            self._ser.reset_input_buffer()
            self._ser.flush()
            out = f"{command}\r".encode()
            # response = await self._ser.awrite_then_readline(out)
            self._ser.write(out)
            response = self._ser.read_until()
            response = response.decode().rstrip("\\n")
            self.logger.debug(f"Sent: {command}. Recieved: {response}")
            # stb = self._ser.awrite_then_readline("?STB\r".encode())
            self._ser.write("?STB\r".encode())
            stb = self._ser.read_until()
            stb = format(int(stb.decode().rstrip("\\n")), "08b")
            keys = ["cmd_err", "exe_err", "sys_err", "laser_on"]
            status = {k: int(stb[::-1][i]) for k, i in zip(keys, [0,1,5,6])}
            self.logger.debug(f"status: {status}")
            self._emission = status.pop("laser_on")
            alarm = [k for k, v in status.items() if v]
        except (UnicodeDecodeError, ValueError) as e:  # try again
            self.logger.error(e)
            await asyncio.sleep(0.5)
            return await self._write(command)
        return response, alarm

    def close(self):
        self._ser.close()
