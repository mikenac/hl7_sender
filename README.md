# HL7 Sender

This repository allows you to send HL7 messages with ease. It includes a Streamlit-based user interface.

## Init
``` uv sync ```

## Usage

### Local (Streamlit)

To start the Streamlit UI locally, run:

```bash
streamlit run streamlit_sender.py
```

### Docker

To build the Docker image:

```bash
make build
```

To run the Docker container (with config.json persisted):

```bash
make run
```