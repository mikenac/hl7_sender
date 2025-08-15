import streamlit as st
import socket

MLLP_START_BLOCK = b'\x0b'
MLLP_END_BLOCK = b'\x1c\r'

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
st.title("📤 HL7 MLLP Test Sender")

col1, col2 = st.columns([1, 1])
host = col1.text_input("Target Host", "127.0.0.1")
port = col2.number_input("Target Port", 2575)

hl7_input = st.text_area("HL7 Message", height=300, placeholder="Paste your HL7 message here...")

if st.button("Send HL7 Message"):
    if not hl7_input.strip():
        st.warning("Please provide a valid HL7 message.")
    else:
        with st.spinner("Sending message..."):
            ack = send_hl7_message(hl7_input, host, port)

        if ack.startswith("Error:"):
            st.error(ack)
        else:
            status = parse_ack_status(ack)
            if status == "AA":
                st.success("✅ ACK Status: AA (Application Accept)")
            elif status == "AE":
                st.error("❌ ACK Status: AE (Application Error)")
            elif status == "AR":
                st.error("❌ ACK Status: AR (Application Reject)")
            else:
                st.warning(f"⚠️ Unknown ACK status: {status}")

            st.subheader("📄 Raw ACK Message")
            st.code(ack, language="hl7")

            st.subheader("📄 Parsed ACK Segments")
            segments = ack.strip().split("\r")
            for segment in segments:
                st.text(segment)
