# Makefile for HL7 Sender

IMAGE_NAME=hl7_sender
TAG=latest

.PHONY: build run

build:
	docker build -t $(IMAGE_NAME):$(TAG) .

run:
	docker run --rm -p 8501:8501 -v $(PWD)/config.json:/app/config.json $(IMAGE_NAME):$(TAG)
