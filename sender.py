import socket
import json
import os

MLLP_START_BLOCK = b'\x0b'
MLLP_END_BLOCK = b'\x1c\r'

# Load HOST and PORT from config.json if available
CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.json')
if os.path.exists(CONFIG_PATH):
    with open(CONFIG_PATH, 'r') as f:
        config = json.load(f)
    HOST = config.get('HOST', '127.0.0.1')
    PORT = config.get('PORT', 2575)
else:
    HOST = '127.0.0.1'
    PORT = 2575

# Sample HL7 message (MSH + PID for test)
hl7_message = (
    "MSH|^~|SENDER|SENDERAPP|RECEIVER|RECEIVERAPP|20250715123000||ADT^A01|MSG00001|P|2.3\r"
    "PID|1||123456^^^MRN||DOE^JOHN||19800101|M|||123 Main St^^Pittsburgh^PA^15213\r"
)

# Wrap with MLLP framing
mllp_message = MLLP_START_BLOCK + hl7_message.encode() + MLLP_END_BLOCK

with socket.create_connection((HOST, PORT), timeout=10) as sock:
    sock.sendall(mllp_message)
    print(f"HL7 message sent to {HOST}:{PORT}.")

    ack_data = b''
    while True:
        chunk = sock.recv(1024)
        if not chunk:
            break
        ack_data += chunk
        if MLLP_END_BLOCK in chunk:
            break

# Strip MLLP envelope
ack = ack_data.strip(MLLP_START_BLOCK + MLLP_END_BLOCK).decode()
print("\nReceived ACK:\n" + ack)
