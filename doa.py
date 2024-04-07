from tuning import Tuning
import usb.core
import usb.util
import time
import socket
import os

dev = usb.core.find(idVendor=0x2886, idProduct=0x0018)
text = ""
# Set the path for the Unix socket
socket_path = '/tmp/AudioTest'

# remove the socket file if it already exists
try:
    os.unlink(socket_path)
except OSError:
    if os.path.exists(socket_path):
        raise

# Create the Unix socket server
server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

# Bind the socket to the path
server.bind(socket_path)

# Listen for incoming connections
server.listen(1)

# accept connections
#print('Server is listening for incoming connections...')
connection, client_address = server.accept()
if dev:
    Mic_tuning = Tuning(dev)
    #print(Mic_tuning.direction) #
    while True:
        try:
            #print(Mic_tuning.direction)
            if (45 < Mic_tuning.direction < 135):
                text = "front"
            elif (Mic_tuning.direction < 45 or Mic_tuning.direction > 320):
                text = "left "
            elif (135 < Mic_tuning.direction < 225):
                text = "right"
            elif (225 < Mic_tuning.direction < 320):
                text = "back "
            connection.send(text.encode('utf-8'))
            time.sleep(1)
        except KeyboardInterrupt:
            break
        except:
            pass
if dev is None:
    ValueError("No dev found")
    
# close the connection
connection.close()
# remove the socket file
os.unlink(socket_path)
