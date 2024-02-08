import unittest
from msp import MspCtr

class TestMainController(unittest.TestCase):
    def test_encode_v1(self):
        msp = MspCtr(None)
        for code in range(256):
            buffer = msp.encode_v1(code)
            self.assertEqual(buffer, bytearray((36, 77, 60, 0, code, code)))

if __name__ == '__main__':
    unittest.main()
