from enum import Enum, IntEnum
from dataclasses import dataclass
from msp_codes import MspCodes

@dataclass
class MspData:
    msp_protocol_version = 0
    api_version = '0.0.0'
    flight_controller_identifier = ''
    flight_controller_version = ''
    version = 0
    build_info = ''
    build_key = ''
    build_options = []
    multi_type = 0
    msp_version = 0 # not specified using semantic versioning
    capability = 0
    cycle_time = 0
    i2c_error = 0
    cpuload = 0
    cpu_temp = 0
    active_sensors = 0
    mode = 0
    profile = 0
    uid = [0, 0, 0]
    accelerometer_trims = [0, 0]
    name = '' # present for backwards compatibility before msp v1.45
    craft_name = ''
    display_name = '' # present for backwards compatibility before msp v1.45
    pilot_name = ''
    pid_profile_names = ['', '', '', '']
    rate_profile_names = ['', '', '', '']
    num_profiles = 3
    rate_profile = 0
    board_type = 0
    arming_disable_count = 0
    arming_disable_flags = 0
    arming_disabled = False
    runaway_takeoff_prevention_disabled = False
    board_identifier = ''
    board_version = 0
    target_capabilities = 0
    target_name = ''
    board_name = ''
    manufacturer_id = ''
    signature = None
    mcu_type_id = 255
    configuration_state = 0
    config_state_flag = 0
    sample_rate_hz = 0
    configuration_problems = 0
    hardware_name = ''


class MspRecType(Enum):
    REQUEST     = '<'
    RESPONSE    = '>'
    UNSUPPORTED = '!'

class TargetCapabilitiesFlags(IntEnum):
    HAS_VCP = 0
    HAS_SOFTSERIAL = 1
    IS_UNIFIED = 2
    HAS_FLASH_BOOTLOADER = 3
    SUPPORTS_CUSTOM_DEFAULTS = 4
    HAS_CUSTOM_DEFAULTS = 5
    SUPPORTS_RX_BIND = 6

class ConfigurationStates(IntEnum):
    DEFAULTS_BARE = 0
    DEFAULTS_CUSTOM = 1
    CONFIGURED = 2

class ResetTypes(IntEnum):
    BASE_DEFAULTS = 0
    CUSTOM_DEFAULTS = 1

class MspRec:
    def __init__(self, buf: bytes) -> None:
        self._idx = 0
        self.type = MspRecType(chr(buf[2]))
        self.code = MspCodes(buf[3])
        self.payload = buf[4: -1]

    def __repr__(self) -> str:
        return f'MspRec type: {self.type.name}, code: {self.code.name}, payload: {self.payload}'

    def __iter__(self):
        self._idx = 0
        return self

    def __next__(self):
        if self._idx == len(self.payload):
            raise StopIteration
        idx = self._idx
        self._idx += 1
        return self.payload[idx]

    def __getitem__(self, index):
        return self.payload[index]

    def read_uint8(self) -> int:
        return next(self, None)

    def read_uint16(self) -> int:
        result = self.uint16(self._idx)
        if result is not None:
            self._idx += 2
        return result

    def read_uint32(self) -> int:
        result = self.uint32(self._idx)
        if result is not None:
            self._idx += 4
        return result

    def read_string(self, count: int = 0) -> str:
        count = count or next(self, 0);
        end = self._idx + count
        if count and end < len(self.payload):
            result = self.payload[self._idx: end].decode()
            self._idx += len(result)
            return result
        return ''

    def uint8(self, idx: int) -> int:
        if idx < len(self.payload):
            return self.payload[idx]
        return None

    def uint16(self, idx: int) -> int:
        if (idx + 1) < len(self.payload):
            return self.payload[idx] | self.payload[idx + 1] << 8
        return None

    def uint32(self, idx: int) -> int:
        if (idx + 3) < len(self.payload):
            return self.uint16(idx) | self.uint16(idx + 2) << 16
        return None
