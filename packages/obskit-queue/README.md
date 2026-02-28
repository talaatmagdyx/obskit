# obskit-queue

Kafka and RabbitMQ message queue tracing and instrumentation for the obskit toolkit.

## Installation

```bash
pip install obskit-queue

# With Kafka support
pip install "obskit-queue[kafka]"

# With RabbitMQ support
pip install "obskit-queue[rabbitmq]"
```

## Features

- **Kafka producer/consumer instrumentation** — Automatic message tracing and metrics
- **RabbitMQ channel instrumentation** — Trace message publish and consume operations
- **Consumer lag monitoring** — Track and alert on consumer group lag
- **Dead letter queue (DLQ) tracking** — Monitor and alert on DLQ depth

## Usage

```python
from obskit.queue import instrument_kafka_producer
from kafka import KafkaProducer

producer = KafkaProducer(bootstrap_servers=["localhost:9092"])
instrumented = instrument_kafka_producer(producer, service_name="order-service")
```

## Part of obskit

This package is part of the [obskit](https://github.com/talaatmagdyx/obskit) monorepo.
