import os
from dotenv import load_dotenv
import socket
import tkinter as tk
import struct
import cv2
import numpy as np
from PIL import ImageTk, Image


load_dotenv()
PI_IP = os.getenv("PI_IP")
CMD_PORT = 5005
VIDEO_PORT = 5006

PAYLOAD_FORMAT = "!Q"
payload_size = struct.calcsize(PAYLOAD_FORMAT)

BASE_SPEED = 200
TURN_SPEED = 150
LEFT_MOTOR_TRIM = 1.00
RIGHT_MOTOR_TRIM = 0.95

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CALIB_PATH = os.path.join(BASE_DIR, 'calibration/')

map_l1 = np.load(f'{CALIB_PATH}calib_map_l1.npy')
map_l2 = np.load(f'{CALIB_PATH}calib_map_l2.npy')
map_r1 = np.load(f'{CALIB_PATH}calib_map_r1.npy')
map_r2 = np.load(f'{CALIB_PATH}calib_map_r2.npy')

cmd_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
current_command_tuple = (0, 0)

video_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
stream_data = b""


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

def process_frame(frame):
    mid = frame.shape[1] // 2

    left = frame[:, :mid]
    right = frame[:, mid:]

    rect_l = cv2.remap(left, map_l1, map_l2, cv2.INTER_LINEAR)
    rect_r = cv2.remap(right, map_r1, map_r2, cv2.INTER_LINEAR)
    
    # TODO add processing and return the processed frame as the last element
    return rect_l, rect_r, rect_l 

def connect_video():
    global video_socket
    try:
        print(f"connecting to {PI_IP}:{VIDEO_PORT}...")
        video_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        video_socket.connect((PI_IP, VIDEO_PORT))
        video_socket.setblocking(False)
        print("video connected")
    except Exception as e:
        print(f'video connection error: {e}')

def update_video_loop():
    global stream_data
    try:
        while True:
            packet = video_socket.recv(4096)
            # if the packet is empty then TCP is closed
            if not packet:
                break
            stream_data += packet
    except BlockingIOError:
        pass
    except Exception as e:
        print(f"stream error: {e}")
        connect_video()
        root.after(33, update_video_loop)
        return

    try:
        while len(stream_data) >= payload_size:
            msg_size = struct.unpack(PAYLOAD_FORMAT, stream_data[:payload_size])[0]
            if len(stream_data) < payload_size + msg_size:
                break

            frame_data = stream_data[payload_size: payload_size + msg_size]
            stream_data = stream_data[payload_size + msg_size:]

            np_arr = np.frombuffer(frame_data, dtype=np.uint8)
            frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            if frame is None: 
                continue
            # the camera is upside down due to the form factor
            frame = cv2.rotate(frame, cv2.ROTATE_180)

            rect_l, rect_r, rect_p = process_frame(frame)
            left_display = cv2.cvtColor(cv2.resize(rect_l, (480, 360)), cv2.COLOR_BGR2RGB)
            right_display = cv2.cvtColor(cv2.resize(rect_r, (480, 360)), cv2.COLOR_BGR2RGB)
            # processed_display = cv2.cvtColor(cv2.resize(rect_p, (480, 360)), cv2.COLOR_BGR2RGB)
            processed_display = cv2.cvtColor(rect_p, cv2.COLOR_BGR2RGB)

            left_img = ImageTk.PhotoImage(image=Image.fromarray(left_display))
            right_img = ImageTk.PhotoImage(image=Image.fromarray(right_display))
            processed_img = ImageTk.PhotoImage(image=Image.fromarray(processed_display))

            left_canvas.imgtk = left_img
            left_canvas.config(image=left_img)
            right_canvas.imgtk = right_img
            right_canvas.config(image=right_img)
            center_canvas.imgtk = processed_img
            center_canvas.config(image=processed_img)

    except Exception as e:
        print(f"frame error: {e}")

    root.after(33, update_video_loop)

root = tk.Tk()
root.title("host control panel")
root.geometry("1050x900")
root.configure(bg="#000000")

canvas_frame = tk.Frame(root, bg="#000000")
canvas_frame.pack()

left_canvas = tk.Label(canvas_frame, bg="#115151", width=480, height=360, relief="solid", bd=1)
left_canvas.grid(row=1, column=0, padx=6, pady=2)
right_canvas = tk.Label(canvas_frame, bg="#511151", width=480, height=360, relief="solid", bd=1)
right_canvas.grid(row=1, column=1, padx=6, pady=2)
center_canvas = tk.Label(canvas_frame, bg="#515111", width=640, height=480, relief="solid", bd=1)
center_canvas.grid(row=3, column=0, columnspan=2, pady=2)

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

root.after(100, connect_video)
root.after(200, update_video_loop)

root.mainloop()

print("shutting down")
try:
    cmd_socket.sendto(b"0,0\n", (PI_IP, CMD_PORT))
    cmd_socket.close()
except Exception as e:
    print(f"exception: {e}")
print("shutdown complete")
