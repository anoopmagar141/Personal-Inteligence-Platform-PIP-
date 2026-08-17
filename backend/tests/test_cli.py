import json

from frontend.cli import pip_cli


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class FakeOpener:
    def __init__(self):
        self.requests = []
        self.responses = []

    def queue(self, payload):
        self.responses.append(payload)

    def __call__(self, req):
        body = json.loads(req.data.decode("utf-8")) if req.data else None
        self.requests.append(
            {
                "method": req.get_method(),
                "url": req.full_url,
                "body": body,
            }
        )
        return FakeResponse(self.responses.pop(0))


def test_profile_commands_call_rest_api():
    opener = FakeOpener()
    opener.queue([{"field": "name", "value": "BatMan"}])
    opener.queue({"status": "updated"})
    opener.queue({"status": "deleted", "field": "answer_depth"})

    assert pip_cli.run_command(["/profile"], opener=opener)[0]["field"] == "name"
    assert pip_cli.run_command(["/profile", "edit", "answer_depth", "brief"], opener=opener)["status"] == "updated"
    assert pip_cli.run_command(["/profile", "delete", "answer_depth"], opener=opener)["status"] == "deleted"

    assert opener.requests[0]["method"] == "GET"
    assert opener.requests[0]["url"].endswith("/memory/profile")
    assert opener.requests[1]["method"] == "POST"
    assert opener.requests[1]["url"].endswith("/memory/correct")
    assert opener.requests[1]["body"] == {"field": "answer_depth", "value": "brief"}
    assert opener.requests[2]["method"] == "DELETE"


def test_decide_and_decisions_commands_call_rest_api():
    opener = FakeOpener()
    opener.queue({"status": "logged", "decision_id": 1})
    opener.queue([{"id": 1}])
    opener.queue([{"id": 1}])
    opener.queue({"status": "updated"})

    assert pip_cli.run_command(["/decide", "We", "will", "use", "SQLite"], opener=opener)["status"] == "logged"
    assert pip_cli.run_command(["/decisions"], opener=opener) == [{"id": 1}]
    assert pip_cli.run_command(["/decisions", "search", "SQLite"], opener=opener) == [{"id": 1}]
    assert pip_cli.run_command(["/decisions", "1", "abandon", "--reason", "changed"], opener=opener)["status"] == "updated"

    assert opener.requests[0]["url"].endswith("/decision/create")
    assert opener.requests[0]["body"]["text"] == "We will use SQLite"
    assert opener.requests[1]["url"].endswith("/decision/search")
    assert opener.requests[2]["url"].endswith("/decision/search?q=SQLite")
    assert opener.requests[3]["method"] == "PATCH"
    assert opener.requests[3]["body"] == {"state": "abandoned", "reason": "changed"}


def test_pending_commands_call_rest_api():
    opener = FakeOpener()
    opener.queue([{"id": 7, "decision_text": "Candidate"}])
    opener.queue([{"id": 7, "decision_text": "Candidate"}])
    opener.queue({"status": "promoted"})
    opener.queue({"status": "dismissed"})

    assert pip_cli.run_command(["/pending"], opener=opener)[0]["id"] == 7
    assert pip_cli.run_command(["/pending", "review", "7"], opener=opener)["decision_text"] == "Candidate"
    assert pip_cli.run_command(["/pending", "promote", "7"], opener=opener)["status"] == "promoted"
    assert pip_cli.run_command(["/pending", "dismiss", "7"], opener=opener)["status"] == "dismissed"

    assert opener.requests[0]["url"].endswith("/decision/pending")
    assert opener.requests[2]["url"].endswith("/decision/pending/7/promote")
    assert opener.requests[3]["url"].endswith("/decision/pending/7/dismiss")


def test_rag_commands_call_rest_api():
    opener = FakeOpener()
    opener.queue({"status": "ingested", "file_path": "C:\\docs\\notes.txt", "chunk_count": 3})
    opener.queue([{"file_path": "C:\\docs\\notes.txt"}])
    opener.queue({"status": "removed", "file_path": "C:\\docs\\notes.txt"})

    ingested = pip_cli.run_command(["/ingest", "C:\\docs\\notes.txt"], opener=opener)
    assert ingested["status"] == "ingested"
    docs = pip_cli.run_command(["/documents"], opener=opener)
    assert docs[0]["file_path"] == "C:\\docs\\notes.txt"
    removed = pip_cli.run_command(["/remove", "C:\\docs\\notes.txt"], opener=opener)
    assert removed["status"] == "removed"

    assert opener.requests[0]["url"].endswith("/rag/ingest")
    assert opener.requests[0]["body"] == {"file_path": "C:\\docs\\notes.txt", "project_id": None}
    assert opener.requests[1]["url"].endswith("/rag/documents")
    assert opener.requests[2]["method"] == "DELETE"
    # Path separators must survive percent-encoding as a single path segment.
    assert "%5C" in opener.requests[2]["url"] or "docs" in opener.requests[2]["url"]
