import numpy as np
import serial
import argparse
import time


def out_sin(x, freq=1):
    return np.sin(2 * np.pi * freq * x)


parser = argparse.ArgumentParser()
parser.add_argument('COM', help="serial port to output data to")
parser.add_argument('--freq', help='sampling freq',
                    default=50)
args = parser.parse_args()

t = 0
dt = 1/args.freq
s = serial.Serial(args.COM)

try:
    while True:
        s.write(f'\t{t}\t*\t{out_sin(t)}\n'.encode())
        t += dt
        time.sleep(dt)
except KeyboardInterrupt:
    s.close()
