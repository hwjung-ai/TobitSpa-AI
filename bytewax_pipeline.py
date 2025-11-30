"""
Minimal Bytewax pipeline stub for CEP:
- Input: simulated events/metrics
- Processing: simple threshold rule
- Output: print or future hook to Postgres/Redis/WebSocket
"""
import json
from datetime import datetime

from bytewax.dataflow import Dataflow
from bytewax.inputs import ManualInputConfig
from bytewax.outputs import StdOutputConfig


def _source_builder(worker_index: int, worker_count: int):
    """Manual input yields a few synthetic events; replace with Kafka/etc."""
    data = [
        {"asset": "web-server-01", "metric": "cpu_usage", "value": 82, "ts": datetime.utcnow().isoformat()},
        {"asset": "db-server-01", "metric": "disk_usage", "value": 91, "ts": datetime.utcnow().isoformat()},
        {"asset": "core-switch-01", "metric": "port_errors", "value": 2, "ts": datetime.utcnow().isoformat()},
    ]
    for item in data:
        yield None, item


def _process_event(event: dict):
    """Apply simple rule; mark alerts."""
    threshold = 80 if event["metric"] == "cpu_usage" else 90 if event["metric"] == "disk_usage" else 10
    event["alert"] = event["value"] >= threshold
    return event


def build_flow():
    flow = Dataflow()
    flow.input("in", ManualInputConfig(_source_builder))
    flow.map(_process_event)
    flow.output("out", StdOutputConfig())
    return flow


if __name__ == "__main__":
    from bytewax.execution import run_main

    run_main(build_flow)
