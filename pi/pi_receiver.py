import socket
import serial
import time
import glob


UDP_IP = "0.0.0.0"
UDP_PORT = 5005
BAUD_RATE = 115200
COMMAND_TIMEOUT = 0.5

def find_arduino_port():
    # detect potential serial devices 
    candidate_ports = glob.glob('/dev/ttyACM*') + glob.glob('/dev/ttyUSB*')
    for port in candidate_ports:
        try:
            ser = serial.Serial(port, BAUD_RATE, timeout=1)
            print(f"connected to Arduino on {port}")
            time.sleep(2)  # bootloader reset
            return ser
        except (serial.SerialException, OSError):
            continue
    return None

# initial serial setup
ser = find_arduino_port()
if ser is None:
    print("could not find Arduino on startup. retrying in main loop")

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((UDP_IP, UDP_PORT))
sock.settimeout(COMMAND_TIMEOUT)

print(f"wireless receiver online. listening on UDP port {UDP_PORT}")

try:
    while True:
        try:
            data, _ = sock.recvfrom(1024)
            command_str = data.decode('utf-8').strip() + "\n"
        except socket.timeout:
            # emergency stop: host disconnected or stopped sending commands
            command_str = "0,0\n"
        except OSError:
            time.sleep(0.1)
            continue

        # write to serial if connected, otherwise attempt reconnection
        if ser and ser.is_open:
            try:
                ser.write(command_str.encode('utf-8'))
                ser.flush()
            except (serial.SerialException, OSError) as e:
                print(f"serial write error ({e}). closing port")
                try:
                    ser.close()
                except Exception:
                    pass
                ser = None
        else:
            # try to recover the serial link
            ser = find_arduino_port()

except KeyboardInterrupt:
    print("shutting down wireless receiver")
finally:
    # ensure motors stop on exit
    if ser and ser.is_open:
        try:
            ser.write(b"0,0\n")
            ser.flush()
            ser.close()
        except Exception:
            pass
    sock.close()
