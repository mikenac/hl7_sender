import socket

MLLP_START_BLOCK = b'\x0b'
MLLP_END_BLOCK = b'\x1c\r'

HOST = '127.0.0.1'  # or the IP where your MLLP listener is running
PORT = 2575         # same port as the listener

# Sample HL7 message (MSH + PID for test)
hl7_message = (
    "MSH|^~|SENDER|SENDERAPP|RECEIVER|RECEIVERAPP|20250715123000||ADT^A01|MSG00001|P|2.3\r"
    "PID|1||123456^^^MRN||DOE^JOHN||19800101|M|||123 Main St^^Pittsburgh^PA^15213\r"
)

# Wrap with MLLP framing
mllp_message = MLLP_START_BLOCK + hl7_message.encode() + MLLP_END_BLOCK

with socket.create_connection((HOST, PORT), timeout=10) as sock:
    sock.sendall(mllp_message)
    print("HL7 message sent.")

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
