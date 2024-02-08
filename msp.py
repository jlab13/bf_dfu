import serial
from semver.version import Version
from msp_codes import MspCodes
from msp_data import MspData, MspRec, ResetTypes, TargetCapabilitiesFlags, ConfigurationStates

# PORT = '/dev/cu.usbmodem0x80000001'
PORT = '/dev/cu.usbmodem355F367335381'
BAUDRATE = 115200


# ReadState = Enum(
#     value='ReadState',
#     names=('IDLE PROTO_IDENTIFIER DIRECTION_V1 DIRECTION_V2 FLAG_V2 PAYLOAD_LENGTH_V1 PAYLOAD_LENGTH_JUMBO_LOW '
#            'PAYLOAD_LENGTH_JUMBO_HIGH PAYLOAD_LENGTH_JUMBO_HIGH PAYLOAD_LENGTH_V2_HIGH CODE_V1 '
#            'CODE_JUMBO_V1 CODE_V2_LOW CODE_V2_HIGH PAYLOAD_V1 PAYLOAD_V2 CHECKSUM_V1 CHECKSUM_V2'),
# )

def bit_check(num: int, bit: int) -> bool:
    return (num >> bit) % 2 != 0


class MspCtr:
    SIGNATURE_LENGTH = 32
    API_VERSION_1_41 = Version(major=1, minor=41)
    API_VERSION_1_42 = Version(major=1, minor=42)
    API_VERSION_1_43 = Version(major=1, minor=43)
    API_VERSION_1_44 = Version(major=1, minor=44)
    API_VERSION_1_45 = Version(major=1, minor=45)
    API_VERSION_1_46 = Version(major=1, minor=46)

    def __init__(self, port: serial.Serial) -> None:
        self.port = port
        self.data = MspData()

    def close(self) -> None:
        self.port.close()

    def encode_v1(self, code: int, *data) -> bytes:
        data_len = 0
        if data:
            data_len = len(data)
        # Header: $M<
        buffer = bytearray((36, 77, 60, data_len, code))
        checksum = buffer[3] ^ buffer[4]
        if data_len:
            for item in data:
                buffer.append(item)
                checksum ^= item
        buffer.append(checksum)
        return bytes(buffer)

    def read(self) -> bytes:
        state = 0
        result = bytearray()
        while True:
            if state < 3:
                byte = self.port.read()
                if state > 0:
                    result.append(byte[0])
                if byte == b'$':
                    result.append(byte[0])
                    state = 1
                    continue
                elif byte == b'M':
                    state = 2
                    continue
                elif byte == b'>':
                    state = 3
                    continue
            else:
                byte = self.port.read()
                result = result + self.port.read(int(byte[0]) + 2)
                break
        return bytes(result)

    def read_rec(self) -> MspRec:
        return MspRec(self.read())

    def send(self, code: int, *data) -> bytes:
        self.port.write(self.encode_v1(code, *data))

    def decode(self, rec: MspRec) -> None:
        match rec.code:
            case MspCodes.MSP_API_VERSION:
                self.data.msp_protocol_version = next(rec)
                self.data.api_version = f'{next(rec)}.{next(rec)}.0'
            case MspCodes.MSP_FC_VARIANT:
                self.data.flight_controller_identifier = rec[:4].decode()
            case MspCodes.MSP_FC_VERSION:
                self.data.flight_controller_version = f'{next(rec)}.{next(rec)}.{next(rec)}'
            case MspCodes.MSP_BUILD_INFO:
                buf = bytearray(rec[:19])
                buf.insert(11, 32)
                self.data.build_info = buf.decode()
            case MspCodes.MSP_BOARD_INFO:
                self.data.board_identifier = rec.read_string(4)
                self.data.board_version = rec.read_uint16()
                self.data.board_type = rec.read_uint8()
                self.data.target_capabilities = rec.read_uint8()
                self.data.target_name = rec.read_string()
                self.data.board_name = rec.read_string()
                self.data.manufacturer_id = rec.read_string()

                self.data.signature = bytearray()
                for _ in range(MspCtr.SIGNATURE_LENGTH):
                    self.data.signature.append(rec.read_uint8())

                self.data.mcu_type_id = rec.read_uint8()

                version = Version.parse(self.data.api_version)
                if version >= MspCtr.API_VERSION_1_42:
                    self.data.configuration_state = rec.read_uint8()
                if version >= MspCtr.API_VERSION_1_43:
                    self.data.sample_rate_hz = rec.read_uint16()
                    self.data.configuration_problems = rec.read_uint32()
                else:
                    self.data.configuration_problems = 0




# MARK: -
def main():
    msp = MspCtr(serial.Serial(PORT, baudrate=BAUDRATE))

    msp.send(MspCodes.MSP_API_VERSION)
    rec = msp.read_rec()
    msp.decode(rec)
    print(msp.data.msp_protocol_version)
    print(msp.data.api_version)
    print('------------------')

    msp.send(MspCodes.MSP_FC_VARIANT)
    rec = msp.read_rec()
    msp.decode(rec)
    print(msp.data.flight_controller_identifier)
    print('------------------')

    msp.send(MspCodes.MSP_FC_VERSION)
    rec = msp.read_rec()
    msp.decode(rec)
    print(msp.data.flight_controller_version)
    print('------------------')

    msp.send(MspCodes.MSP_BUILD_INFO)
    rec = msp.read_rec()
    msp.decode(rec)
    print(msp.data.build_info)
    print('------------------')

    msp.send(MspCodes.MSP_BOARD_INFO)
    rec = msp.read_rec()
    msp.decode(rec)
    print(msp.data.board_identifier)
    print(msp.data.board_version)
    print(msp.data.board_type)
    print(msp.data.target_capabilities)
    print(msp.data.target_name)
    print(msp.data.board_name)
    print(msp.data.manufacturer_id)
    print(msp.data.signature.hex())
    print(msp.data.mcu_type_id)
    print(msp.data.configuration_state)
    print(msp.data.sample_rate_hz)
    print(msp.data.configuration_problems)

    print('------------------')

    r = bit_check(msp.data.target_capabilities, TargetCapabilitiesFlags.SUPPORTS_CUSTOM_DEFAULTS) \
        and bit_check(msp.data.target_capabilities, TargetCapabilitiesFlags.HAS_CUSTOM_DEFAULTS) \
        and msp.data.configuration_state == ConfigurationStates.DEFAULTS_BARE
    print(r)

    # msp.send(MspCodes.MSP_RESET_CONF, ResetTypes.CUSTOM_DEFAULTS)
    # rec = msp.read_rec()
    # print(f'Set defaults done! {rec}')

    # print(bit_check(msp.data.target_capabilities, TargetCapabilitiesFlags.SUPPORTS_CUSTOM_DEFAULTS))
    # print(bit_check(msp.data.target_capabilities, TargetCapabilitiesFlags.HAS_CUSTOM_DEFAULTS))
    # print(msp.data.configuration_state)

    msp.close()

if __name__ == "__main__":
    main()
