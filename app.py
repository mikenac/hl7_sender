import streamlit as st
import socket
import json
import os

MLLP_START_BLOCK = b'\x0b'
MLLP_END_BLOCK = b'\x1c\r'

CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.json')

def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r') as f:
            config = json.load(f)
        return config.get('HOST', 'host.docker.internal'), config.get('PORT', 2575)
    return 'host.docker.internal', 2575

def save_config(host, port):
    with open(CONFIG_PATH, 'w') as f:
        json.dump({'HOST': host, 'PORT': port}, f, indent=2)

def send_hl7_message(message: str, host: str, port: int, timeout=10):
    """Send HL7 message via MLLP and receive ACK."""
    mllp_message = MLLP_START_BLOCK + message.encode() + MLLP_END_BLOCK

    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            sock.sendall(mllp_message)
            ack_data = b''
            while True:
                chunk = sock.recv(1024)
                if not chunk:
                    break
                ack_data += chunk
                if MLLP_END_BLOCK in chunk:
                    break
        ack = ack_data.strip(MLLP_START_BLOCK + MLLP_END_BLOCK).decode()
        return ack
    except Exception as e:
        return f"Error: {e}"

def parse_ack_status(ack_message: str):
    """Return ACK status (AA, AE, AR) if available."""
    for line in ack_message.strip().split("\r"):
        if line.startswith("MSA"):
            fields = line.split("|")
            return fields[1] if len(fields) > 1 else "UNKNOWN"
    return "UNKNOWN"

# --- Streamlit UI ---
st.set_page_config(page_title="HL7 MLLP Test Sender", layout="wide")
st.title("\U0001F4E4 HL7 MLLP Test Sender")

default_host, default_port = load_config()
col1, col2 = st.columns([1, 1])
host = col1.text_input("Target Host", default_host)
port = col2.number_input("Target Port", int(default_port))

if st.button("Save Host/Port as Default"):
    save_config(host, int(port))
    st.success(f"Saved default HOST={host}, PORT={int(port)}.")

hl7_input = st.text_area("HL7 Message", height=300, placeholder="Paste your HL7 message here...")

if st.button("Send HL7 Message"):
    if not hl7_input.strip():
        st.warning("Please provide a valid HL7 message.")
    else:
        with st.spinner("Sending message..."):
            ack = send_hl7_message(hl7_input, host, int(port))

        if ack.startswith("Error:"):
            st.error(ack)
        else:
            status = parse_ack_status(ack)
            if status == "AA":
                st.success("\u2705 ACK Status: AA (Application Accept)")
            elif status == "AE":
                st.error("\u274c ACK Status: AE (Application Error)")
            elif status == "AR":
                st.error("\u274c ACK Status: AR (Application Reject)")
            else:
                st.warning(f"\u26a0\ufe0f Unknown ACK status: {status}")

            st.subheader("\U0001F4C4 Raw ACK Message")
            st.code(ack, language="hl7")

            st.subheader("\U0001F4C4 Parsed ACK Segments")
            segments = ack.strip().split("\r")
            for segment in segments:
                st.text(segment)
