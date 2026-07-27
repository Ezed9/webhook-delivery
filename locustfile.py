import os
import uuid

from locust import HttpUser, between, task

API_KEY = os.environ["API_KEY"]
ENDPOINT_ID = os.environ["ENDPOINT_ID"]


class Producer(HttpUser):
    wait_time = between(0.01, 0.1)

    @task
    def post_event(self) -> None:
        self.client.post(
            "/events",
            json={
                "endpoint_id": ENDPOINT_ID,
                "event_type": "load.test",
                "payload": {"k": "v"},
            },
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Idempotency-Key": str(uuid.uuid4()),
            },
        )
