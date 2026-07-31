import cv2
import socket
import struct
import time


HOST = '0.0.0.0'
PORT = 5006
DEV_PATH = '/dev/v4l/by-id/usb-STYT_241029_K_USB_Camera_01.00.00-video-index0'

def get_camera_stream():
    # try to open the VideoCapture stream until the hardware is ready
    while True:
        cap = cv2.VideoCapture(DEV_PATH)
        if cap.isOpened():
            # double width because the frames are stitched side by side
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 2 * 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            print("camera hardware initialized successfully")
            return cap
        print("waiting for stereo camera device")
        cap.release()
        time.sleep(2)

server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server_socket.bind((HOST, PORT))
server_socket.listen(1)

print(f"video server online. listening on port {PORT}")

try:
    while True:
        client_socket, addr = server_socket.accept()
        print(f"video client connected from: {addr}")
        cap = get_camera_stream()
        
        try:
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    print("failed to grab a frame from camera")
                    break
                
                # compress frame to reduce latency (impacts depth estimation)
                _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                data = buffer.tobytes()
                message_size = struct.pack("!Q", len(data))
                client_socket.sendall(message_size + data)
                
        except (ConnectionResetError, BrokenPipeError, socket.error):
            print("client disconnected from video stream")
        finally:
            cap.release()
            client_socket.close()

except KeyboardInterrupt:
    print("shutting down video server")
finally:
    server_socket.close()
