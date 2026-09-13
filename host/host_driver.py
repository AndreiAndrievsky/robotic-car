import os
from dotenv import load_dotenv
import socket
import tkinter as tk


load_dotenv()
PI_IP = os.getenv("PI_IP")
CMD_PORT = 5005
VIDEO_PORT = 5006

BASE_SPEED = 200
TURN_SPEED = 150
LEFT_MOTOR_TRIM = 1.00
RIGHT_MOTOR_TRIM = 0.95

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CALIB_PATH = os.path.join(BASE_DIR, 'calibration/')


cmd_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
current_command_tuple = (0, 0)


def send_motor_packet(left_val, right_val):
    global current_command_tuple
    if current_command_tuple != (left_val, right_val):
        cal_l = int(left_val * LEFT_MOTOR_TRIM)
        cal_r = int(right_val * RIGHT_MOTOR_TRIM)
        try:
            cmd_socket.sendto(f"{cal_l},{cal_r}\n".encode(), (PI_IP, CMD_PORT))
            current_command_tuple = (left_val, right_val)
        except Exception as e:
            print(f"motor packet error: {e}")


root = tk.Tk()
root.title("host control panel")
root.geometry("800x500+10+10")
root.configure(bg="#000000")

KEY_MAPPINGS = {
    'w': (BASE_SPEED, BASE_SPEED),
    's': (-BASE_SPEED, -BASE_SPEED),
    'a': (-TURN_SPEED, TURN_SPEED),
    'd': (TURN_SPEED, -TURN_SPEED),
}

for key, (left, right) in KEY_MAPPINGS.items():
    for k in (key.lower(), key.upper()):
        root.bind(f'<KeyPress-{k}>', lambda e, l=left, r=right: send_motor_packet(l, r))
        root.bind(f'<KeyRelease-{k}>', lambda e: send_motor_packet(0, 0))

# emergency stop
root.bind('<space>', lambda e: send_motor_packet(0, 0))


root.mainloop()

print("shutting down")
try:
    cmd_socket.sendto(b"0,0\n", (PI_IP, CMD_PORT))
    cmd_socket.close()
except Exception as e:
    print(f"exception: {e}")
print("shutdown complete")
