# Makefile for HL7 Sender

IMAGE_NAME=mnacey/hl7_sender
TAG=latest

.PHONY: build run run-local test

build:
	docker build -t $(IMAGE_NAME):$(TAG) .

run:
	docker run --rm -p 8501:8501 -v $(PWD)/config.json:/app/config.json $(IMAGE_NAME):$(TAG)

run-local:
	uv run streamlit run app.py

test:
	uv run pytest test_app.py -v
