import numpy as np

N = 360
DAC_min, DAC_max = 0, 4095  # Arduino Due has 12-bit DAC
f = 1  # Hz

# sin wave
t = np.linspace(0, 1, N)
s = np.sin(2 * np.pi * t * f)
s_ = np.interp(s, [-1, 1], [DAC_min, DAC_max])
s_ = np.array(s_, dtype=int)

print(list(s_))
