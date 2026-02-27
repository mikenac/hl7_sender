import json
import os
import socket
import tempfile
from unittest.mock import patch, MagicMock

import pytest

from app import (
    MLLP_START_BLOCK,
    MLLP_END_BLOCK,
    load_config,
    save_config,
    send_hl7_message,
    parse_ack_status,
    split_hl7_messages,
    with_message_control_id,
    build_fake_ack,
)

# -- Sample HL7 messages used across tests --

SAMPLE_MSH = (
    "MSH|^~\\&|SendingApp|SendingFac|RecvApp|RecvFac|20250101120000||ADT^A01|12345|P|2.3"
)
SAMPLE_MESSAGE = f"{SAMPLE_MSH}\rPID|1||12345^^^MRN||Doe^John"
SAMPLE_ACK = "MSH|^~\\&|RecvApp|RecvFac|SendingApp|SendingFac|20250101120001||ACK^A01|99999|P|2.3\rMSA|AA|12345\r"


# ============================================================
# parse_ack_status
# ============================================================

class TestParseAckStatus:
    def test_aa_status(self):
        ack = "MSH|^~\\&|A|B|C|D|20250101||ACK|1|P|2.3\rMSA|AA|12345\r"
        assert parse_ack_status(ack) == "AA"

    def test_ae_status(self):
        ack = "MSH|^~\\&|A|B|C|D|20250101||ACK|1|P|2.3\rMSA|AE|12345\r"
        assert parse_ack_status(ack) == "AE"

    def test_ar_status(self):
        ack = "MSH|^~\\&|A|B|C|D|20250101||ACK|1|P|2.3\rMSA|AR|12345\r"
        assert parse_ack_status(ack) == "AR"

    def test_no_msa_returns_unknown(self):
        assert parse_ack_status("MSH|^~\\&|A|B\r") == "UNKNOWN"

    def test_empty_string_returns_unknown(self):
        assert parse_ack_status("") == "UNKNOWN"

    def test_msa_with_no_fields_returns_unknown(self):
        assert parse_ack_status("MSA") == "UNKNOWN"


# ============================================================
# split_hl7_messages
# ============================================================

class TestSplitHl7Messages:
    def test_single_message(self):
        msgs = split_hl7_messages("MSH|^~\\&|A\nPID|1||123")
        assert len(msgs) == 1
        assert msgs[0] == "MSH|^~\\&|A\rPID|1||123"

    def test_two_messages(self):
        raw = "MSH|^~\\&|A\nPID|1\nMSH|^~\\&|B\nPID|2"
        msgs = split_hl7_messages(raw)
        assert len(msgs) == 2
        assert msgs[0] == "MSH|^~\\&|A\rPID|1"
        assert msgs[1] == "MSH|^~\\&|B\rPID|2"

    def test_blank_lines_ignored(self):
        raw = "MSH|^~\\&|A\n\n\nPID|1\n\n"
        msgs = split_hl7_messages(raw)
        assert len(msgs) == 1
        assert "PID|1" in msgs[0]

    def test_no_msh_fallback(self):
        raw = "some random text"
        msgs = split_hl7_messages(raw)
        assert len(msgs) == 1
        assert msgs[0] == "some random text"

    def test_empty_input(self):
        assert split_hl7_messages("") == []
        assert split_hl7_messages("   ") == []

    def test_three_messages(self):
        raw = "MSH|A\nPID|1\nMSH|B\nPV1|2\nMSH|C\nOBX|3"
        msgs = split_hl7_messages(raw)
        assert len(msgs) == 3


# ============================================================
# with_message_control_id
# ============================================================

class TestWithMessageControlId:
    def test_sets_msh10(self):
        result = with_message_control_id(SAMPLE_MESSAGE, "NEW_ID")
        segments = result.split("\r")
        msh_fields = segments[0].split("|")
        assert msh_fields[9] == "NEW_ID"

    def test_preserves_other_fields(self):
        result = with_message_control_id(SAMPLE_MESSAGE, "NEW_ID")
        segments = result.split("\r")
        msh_fields = segments[0].split("|")
        assert msh_fields[2] == "SendingApp"
        assert msh_fields[3] == "SendingFac"
        assert "PID|1||12345^^^MRN||Doe^John" in result

    def test_pads_short_msh(self):
        short_msh = "MSH|^~\\&|App"
        result = with_message_control_id(short_msh, "PADDED_ID")
        fields = result.split("|")
        assert fields[9] == "PADDED_ID"

    def test_no_msh_returns_unchanged(self):
        msg = "PID|1||123"
        assert with_message_control_id(msg, "ID") == msg

    def test_replaces_existing_msh10(self):
        result = with_message_control_id(SAMPLE_MESSAGE, "REPLACED")
        msh_fields = result.split("\r")[0].split("|")
        assert msh_fields[9] == "REPLACED"


# ============================================================
# build_fake_ack
# ============================================================

class TestBuildFakeAck:
    def test_returns_aa_status(self):
        ack = build_fake_ack(SAMPLE_MESSAGE, "CTRL_ID")
        assert parse_ack_status(ack) == "AA"

    def test_contains_msa_segment(self):
        ack = build_fake_ack(SAMPLE_MESSAGE, "CTRL_ID")
        assert "\rMSA|" in ack

    def test_uses_provided_message_id(self):
        ack = build_fake_ack(SAMPLE_MESSAGE, "MY_CTRL")
        msa_line = [s for s in ack.split("\r") if s.startswith("MSA")][0]
        assert "MY_CTRL" in msa_line

    def test_swaps_sending_and_receiving(self):
        ack = build_fake_ack(SAMPLE_MESSAGE, None)
        msh_fields = ack.split("\r")[0].split("|")
        # Receiving app/fac from original becomes sending in ACK
        assert msh_fields[2] == "RecvApp"
        assert msh_fields[3] == "RecvFac"
        assert msh_fields[4] == "SendingApp"
        assert msh_fields[5] == "SendingFac"

    def test_ack_message_type(self):
        ack = build_fake_ack(SAMPLE_MESSAGE, None)
        msh_fields = ack.split("\r")[0].split("|")
        assert msh_fields[8] == "ACK^A01"

    def test_no_msh_defaults(self):
        ack = build_fake_ack("PID|1||123", None)
        assert parse_ack_status(ack) == "AA"
        assert ack.startswith("MSH|")

    def test_none_message_id_uses_original_msh10(self):
        ack = build_fake_ack(SAMPLE_MESSAGE, None)
        msa_line = [s for s in ack.split("\r") if s.startswith("MSA")][0]
        assert "12345" in msa_line


# ============================================================
# send_hl7_message (mocked socket)
# ============================================================

class TestSendHl7Message:
    def test_successful_send_and_receive(self):
        ack_bytes = MLLP_START_BLOCK + SAMPLE_ACK.encode() + MLLP_END_BLOCK
        mock_sock = MagicMock()
        mock_sock.recv.side_effect = [ack_bytes, b'']

        with patch("app.socket.create_connection") as mock_conn:
            mock_conn.return_value.__enter__ = MagicMock(return_value=mock_sock)
            mock_conn.return_value.__exit__ = MagicMock(return_value=False)
            result = send_hl7_message("MSH|test", "localhost", 2575)

        assert "MSA|AA" in result
        mock_sock.sendall.assert_called_once()
        sent = mock_sock.sendall.call_args[0][0]
        assert sent.startswith(MLLP_START_BLOCK)
        assert sent.endswith(MLLP_END_BLOCK)

    def test_connection_error_returns_error_string(self):
        with patch("app.socket.create_connection", side_effect=ConnectionRefusedError("refused")):
            result = send_hl7_message("MSH|test", "localhost", 9999)
        assert result.startswith("Error:")

    def test_timeout_returns_error_string(self):
        with patch("app.socket.create_connection", side_effect=socket.timeout("timed out")):
            result = send_hl7_message("MSH|test", "localhost", 2575, timeout=1)
        assert result.startswith("Error:")

    def test_mllp_framing(self):
        mock_sock = MagicMock()
        mock_sock.recv.side_effect = [MLLP_START_BLOCK + b"ACK" + MLLP_END_BLOCK]

        with patch("app.socket.create_connection") as mock_conn:
            mock_conn.return_value.__enter__ = MagicMock(return_value=mock_sock)
            mock_conn.return_value.__exit__ = MagicMock(return_value=False)
            send_hl7_message("HELLO", "localhost", 2575)

        sent = mock_sock.sendall.call_args[0][0]
        assert sent == b'\x0bHELLO\x1c\r'


# ============================================================
# load_config / save_config
# ============================================================

class TestConfig:
    def test_save_and_load_roundtrip(self, tmp_path):
        config_file = tmp_path / "config.json"
        with patch("app.CONFIG_PATH", str(config_file)):
            save_config("myhost", 1234)
            host, port = load_config()
        assert host == "myhost"
        assert port == 1234

    def test_load_defaults_when_missing(self, tmp_path):
        config_file = tmp_path / "nonexistent.json"
        with patch("app.CONFIG_PATH", str(config_file)):
            host, port = load_config()
        assert host == "host.docker.internal"
        assert port == 2575

    def test_save_overwrites(self, tmp_path):
        config_file = tmp_path / "config.json"
        with patch("app.CONFIG_PATH", str(config_file)):
            save_config("first", 1111)
            save_config("second", 2222)
            host, port = load_config()
        assert host == "second"
        assert port == 2222
