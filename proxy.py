import os
import threading
import serial


SRC_PORT = '/dev/ttyAMA0' # mac
DST_PORT = '/dev/ttyACM0' # betaflight
BAUDRATE = 115200

src = serial.Serial(SRC_PORT, baudrate=BAUDRATE)
dst = serial.Serial(DST_PORT, baudrate=BAUDRATE)
is_work = True

def src2dst():
    global is_work
    dump = os.open('src2dst.dat', os.O_WRONLY | os.O_CREAT)
    while is_work:
        try:
            byte = src.read()
            dst.write(byte)
            os.write(dump, byte)
            os.sync()
        except Exception as e:
            os.sync()
            print(e)
            is_work = False

def dst2src():
    global is_work
    dump = os.open('dst2src.dat', os.O_WRONLY | os.O_CREAT)
    while is_work:
        try:
            byte = dst.read()
            src.write(byte)
            os.write(dump, byte)
        except Exception as e:
            os.sync()
            print(e)
            is_work = False

try:
    th1 = threading.Thread(target=src2dst, name='src2dst')
    th2 = threading.Thread(target=dst2src, name='dst2src')

    th1.start()
    th2.start()
    th2.join()
except KeyboardInterrupt:
    is_work = False
finally:
    os.sync()
    dst.close()
    src.close()
