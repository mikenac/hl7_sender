import streamlit as st
import socket
import json
import os
import time
import pandas as pd
import uuid

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

def split_hl7_messages(raw_input: str):
    """
    Split pasted HL7 text into individual messages using lines that start with MSH as boundaries.
    Falls back to one message if no MSH is found.
    """
    lines = [line.strip() for line in raw_input.splitlines() if line.strip()]
    messages = []
    current = []

    for line in lines:
        if line.startswith("MSH"):
            if current:
                messages.append("\r".join(current))
                current = []
        current.append(line)

    if current:
        messages.append("\r".join(current))

    if not messages and raw_input.strip():
        messages.append(raw_input.strip())

    return messages

def with_message_control_id(message: str, message_id: str):
    """Return message with MSH-10 set to message_id when MSH is present."""
    segments = message.split("\r")
    for idx, segment in enumerate(segments):
        if segment.startswith("MSH") and len(segment) >= 4:
            field_sep = segment[3]
            fields = segment.split(field_sep)
            while len(fields) <= 9:
                fields.append("")
            fields[9] = message_id
            segments[idx] = field_sep.join(fields)
            return "\r".join(segments)
    return message

def build_fake_ack(message: str, message_id: str | None):
    """Build a minimal AA ACK using the inbound MSH fields when available."""
    ack_time = time.strftime("%Y%m%d%H%M%S")
    segments = message.split("\r")
    msh = next((s for s in segments if s.startswith("MSH")), "")
    if msh:
        field_sep = msh[3]
        fields = msh.split(field_sep)
        encoding_chars = fields[1] if len(fields) > 1 and fields[1] else "^~\\&"
        comp_sep = encoding_chars[0] if encoding_chars else "^"
        sending_app = fields[2] if len(fields) > 2 else ""
        sending_fac = fields[3] if len(fields) > 3 else ""
        recv_app = fields[4] if len(fields) > 4 else ""
        recv_fac = fields[5] if len(fields) > 5 else ""
        msg_type = fields[8] if len(fields) > 8 else ""
        processing_id = fields[11] if len(fields) > 11 else "P"
        version_id = fields[12] if len(fields) > 12 else "2.3"
        msg_type_comps = msg_type.split(comp_sep) if msg_type else []
        ack_msg_type = comp_sep.join(["ACK"] + msg_type_comps[1:]) if msg_type_comps else "ACK"
    else:
        field_sep = "|"
        encoding_chars = "^~\\&"
        comp_sep = "^"
        sending_app = ""
        sending_fac = ""
        recv_app = ""
        recv_fac = ""
        processing_id = "P"
        version_id = "2.3"
        ack_msg_type = "ACK"
    ack_id = uuid.uuid4().hex
    control_id = message_id or (fields[9] if msh and len(fields) > 9 else "")
    return (
        f"MSH{field_sep}{encoding_chars}{field_sep}{recv_app}{field_sep}{recv_fac}"
        f"{field_sep}{sending_app}{field_sep}{sending_fac}{field_sep}{ack_time}"
        f"{field_sep}{field_sep}{ack_msg_type}{field_sep}{ack_id}{field_sep}{processing_id}"
        f"{field_sep}{version_id}\r"
        f"MSA{field_sep}AA{field_sep}{control_id}\r"
    )

# --- Streamlit UI ---
st.set_page_config(page_title="HL7 MLLP Test Sender", layout="wide")
st.title("\U0001F4E4 HL7 MLLP Test Sender")

if "metrics_history" not in st.session_state:
    st.session_state["metrics_history"] = []

default_host, default_port = load_config()
col1, col2, col3 = st.columns([1, 1, 1])
host = col1.text_input("Target Host", default_host)
port = col2.number_input("Target Port", value=int(default_port), step=1)
repeat_count = col3.number_input("Repeat Count", min_value=1, value=1, step=1)
generate_message_id = st.checkbox(
    "Generate unique message control ID (MSH-10) per send",
    value=False,
    help="When enabled, each send attempt gets a new MSH-10."
)
simulate_ack = st.checkbox(
    "Simulate ACK (no network send)",
    value=False,
    help="When enabled, returns a fake ACK without opening a socket."
)

if st.button("Save Host/Port as Default"):
    save_config(host, int(port))
    st.success(f"Saved default HOST={host}, PORT={int(port)}.")

hl7_input = st.text_area("HL7 Message", height=300, placeholder="Paste your HL7 message here...")
uploaded_file = st.file_uploader("Or upload HL7 text file", type=["txt", "hl7"], accept_multiple_files=False)

if st.button("Send HL7 Message"):
    batch_start_time = time.perf_counter()
    per_attempt_durations = []
    file_content = ""
    if uploaded_file:
        file_content = uploaded_file.getvalue().decode("utf-8", errors="replace")

    input_source = file_content if file_content.strip() else hl7_input
    hl7_messages = split_hl7_messages(input_source)
    if not hl7_messages:
        st.warning("Please provide a valid HL7 message via text or file upload.")
    else:
        ack_records = []
        error_message = None
        with st.spinner(f"Sending message {int(repeat_count)} time(s)..."):
            for msg_idx, message in enumerate(hl7_messages, start=1):
                for attempt in range(1, int(repeat_count) + 1):
                    attempt_start = time.perf_counter()
                    message_to_send = message
                    message_id = None
                    if generate_message_id:
                        message_id = uuid.uuid4().hex
                        message_to_send = with_message_control_id(message_to_send, message_id)
                    if simulate_ack:
                        ack = build_fake_ack(message_to_send, message_id)
                    else:
                        ack = send_hl7_message(message_to_send, host, int(port))
                    attempt_duration = time.perf_counter() - attempt_start
                    if ack.startswith("Error:"):
                        error_message = f"Message {msg_idx}, Attempt {attempt}: {ack}"
                        break
                    ack_records.append({
                        "message_idx": msg_idx,
                        "attempt": attempt,
                        "ack": ack,
                        "message_id": message_id,
                        "duration": attempt_duration
                    })
                    per_attempt_durations.append(attempt_duration)
                if error_message:
                    break
        batch_end_time = time.perf_counter()

        if ack_records:
            attempts_info = f"Sent {len(ack_records)} message attempt(s) successfully."
            total_expected = len(hl7_messages) * int(repeat_count)
            if total_expected > len(ack_records):
                attempts_info += " Stopped early due to an error."
            st.info(attempts_info)

            last_ack = ack_records[-1]["ack"]
            last_message_id = ack_records[-1]["message_id"]
            status = parse_ack_status(last_ack)
            if status == "AA":
                st.success("\u2705 ACK Status: AA (Application Accept)")
            elif status == "AE":
                st.error("\u274c ACK Status: AE (Application Error)")
            elif status == "AR":
                st.error("\u274c ACK Status: AR (Application Reject)")
            else:
                st.warning(f"\u26a0\ufe0f Unknown ACK status: {status}")
            if last_message_id:
                st.info(f"Last sent Message Control ID (MSH-10): {last_message_id}")

            header_suffix = " (Last Attempt)" if int(repeat_count) > 1 else ""
            st.subheader(f"\U0001F4C4 Raw ACK Message{header_suffix}")
            st.code(last_ack, language="hl7")

            st.subheader(f"\U0001F4C4 Parsed ACK Segments{header_suffix}")
            segments = last_ack.strip().split("\r")
            for segment in segments:
                st.text(segment)

            if int(repeat_count) > 1 or len(hl7_messages) > 1:
                st.subheader("\U0001F4CA ACK Summary")
                summary_rows = []
                had_failures = False
                for record in ack_records:
                    preview = record["ack"].replace("\r", "\\r")
                    status = parse_ack_status(record["ack"])
                    status_label = {
                        "AA": "\u2705 AA (Accept)",
                        "AE": "\u26a0\ufe0f AE (Error)",
                        "AR": "\u274c AR (Reject)"
                    }.get(status, "\u26a0\ufe0f Unknown")
                    if status != "AA":
                        had_failures = True
                    summary_rows.append({
                        "Message": record["message_idx"],
                        "Attempt": record["attempt"],
                        "MSH-10": record["message_id"] or "",
                        "Status": status_label,
                        "ACK Preview": (preview[:120] + "…") if len(preview) > 120 else preview
                    })
                st.dataframe(summary_rows, hide_index=True, use_container_width=True, height=240)
                if had_failures:
                    st.warning("Some ACKs indicate errors or rejects. Check the summary and raw ACK for details.")

            total_attempts = len(ack_records)
            total_elapsed = max(batch_end_time - batch_start_time, 0)
            messages_per_sec = (total_attempts / total_elapsed) if total_elapsed > 0 else 0
            avg_time_ms = (sum(per_attempt_durations) / total_attempts * 1000) if total_attempts else 0

            st.subheader("\U0001F4C8 Metrics")
            mcol1, mcol2 = st.columns(2)
            mcol1.metric("Messages/sec", f"{messages_per_sec:.2f}")
            mcol2.metric("Avg send time (ms)", f"{avg_time_ms:.2f}")

            st.session_state["metrics_history"].append({
                "timestamp": time.strftime("%H:%M:%S"),
                "messages_per_sec": messages_per_sec,
                "avg_time_ms": avg_time_ms
            })
            history_df = pd.DataFrame(st.session_state["metrics_history"])
            if not history_df.empty:
                st.line_chart(history_df.set_index("timestamp"))

        if error_message:
            st.error(error_message)
