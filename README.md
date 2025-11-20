# HL7 Sender

This repository provides a Streamlit UI to send HL7 messages over MLLP, view ACKs, and track basic throughput metrics.

## Init
``` uv sync ```

## Usage

### Local (Streamlit)

To start the Streamlit UI locally, run:

```bash
streamlit run app.py
```

Key UI features:
- Send HL7 over MLLP with configurable host/port; persist defaults to `config.json`.
- Paste a single message, multiple messages (detected by `MSH`), or upload a `.txt/.hl7` file.
- Repeat each message N times; view raw ACK, parsed segments, and a scrollable summary grid with status (AA/AE/AR) per attempt.
- Highlight when any ACKs fail without blocking other sends.
- Metrics section showing messages/sec and average send time per attempt, plus a chart of recent runs (session-scoped).

### Examples
Single message:
```
MSH|^~\&|SND|SNDAPP|RCV|RCVAPP|20240101010101||ADT^A01|MSG00001|P|2.5
PID|1||12345^^^HOSP^MR||Doe^John
```

Multiple messages (two `MSH` blocks in one paste or file):
```
MSH|^~\&|SND|SNDAPP|RCV|RCVAPP|20240101010101||ADT^A01|MSG00001|P|2.5
PID|1||12345^^^HOSP^MR||Doe^John
MSH|^~\&|SND|SNDAPP|RCV|RCVAPP|20240101010202||ADT^A03|MSG00002|P|2.5
PID|1||67890^^^HOSP^MR||Smith^Jane
```

Typical ACK snippets:
```
MSH|^~\&|RCV|RCVAPP|SND|SNDAPP|20240101010102||ACK^A01|ACK00001|P|2.5
MSA|AA|MSG00001

MSH|^~\&|RCV|RCVAPP|SND|SNDAPP|20240101010203||ACK^A03|ACK00002|P|2.5
MSA|AE|MSG00002
```

### Configuration and ports
- Default target: `host.docker.internal:2575`. Change host/port in the UI and click “Save Host/Port as Default” to persist to `config.json`.
- Ensure the target port is reachable from where Streamlit is running (firewall/VPN/Docker networking).
- MLLP only; no TLS or auth is implemented.

### Batching semantics
- Repeat count applies to each message independently (e.g., 2 messages x repeat 3 = up to 6 attempts).
- If an attempt errors, remaining repeats for that message are skipped, but prior attempts are kept.
- Summary grid shows Message index (1-based), Attempt number, status, and an ACK preview.

### Metrics behavior
- Metrics are per send action and session-scoped only (not persisted).
- Messages/sec = successful attempts / wall time of the send batch.
- Average send time is per-attempt duration in milliseconds.

### Docker

To build the Docker image:

```bash
make build
```

To run the Docker container (with config.json persisted):

```bash
make run
```

Also available on DockerHub:
``` docker pull mnacey/hl7_sender ```

Common `docker run` example (if not using `make`):
```bash
docker run --rm -p 8501:8501 -v $(pwd)/config.json:/app/config.json teletracking/hl7_sender:latest
```

### Troubleshooting
- Connection refused/timeouts: verify host/port reachability from your machine/container; check firewall/VPN.
- No ACK status shown: ensure the ACK contains an `MSA` segment and the target speaks MLLP framing (no TLS).
- Multiple messages not detected: confirm each message starts with an `MSH` line.
- Garbled characters: uploads are decoded as UTF-8 with replacement; ensure the source is UTF-8.
