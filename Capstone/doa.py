from tuning import Tuning
import usb.core
import usb.util
import time

dev = usb.core.find(idVendor=0x2886, idProduct=0x0018)

if dev:
    Mic_tuning = Tuning(dev)
    print(Mic_tuning.direction) #
    while True:
        try:
            print(Mic_tuning.direction)
            time.sleep(1)
        except KeyboardInterrupt:
            break
if dev is None:
    ValueError("No dev found")