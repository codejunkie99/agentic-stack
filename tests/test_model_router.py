import base64
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from harness_manager.loops.process import ProcessResult
from harness_manager.workspaces.attachments import decode_attachments, public_attachments, stage_attachments
from harness_manager.workspaces.model_router import recommend, routing_policy
from harness_manager.workspaces.service import WorkspaceService
from test_conversations import wait_for_task


CATALOG = [
    {"id": "gpt-5.3-codex-spark", "runner": "codex", "name": "Spark", "efforts": ["low"]},
    {"id": "gpt-5.6-luna", "runner": "codex", "name": "Luna", "efforts": ["low", "medium"]},
    {"id": "gpt-5.6-terra", "runner": "codex", "name": "Terra", "efforts": ["low", "medium", "high"]},
    {"id": "gpt-6-astra", "runner": "codex", "name": "Astra", "efforts": ["medium", "high", "xhigh"]},
]


def test_router_uses_live_catalog_policy_complexity_and_media_capability():
    quick = recommend("codex", "Quickly rename this symbol", "auto:balanced", CATALOG)
    assert quick["model"] == "gpt-5.3-codex-spark" and quick["effort"] == "low"
    deep = recommend("codex", "Audit and refactor the entire app end-to-end", "auto:balanced", CATALOG)
    assert deep["model"] == "gpt-6-astra" and deep["effort"] == "xhigh"
    visual = recommend("codex", "Quickly inspect this", "auto:cost", CATALOG, [{"kind": "image"}])
    assert visual["model"] == "gpt-5.6-luna"
    assert "attached image" in visual["reason"]
    assert visual["fallback"] is False and visual["candidateCount"] == 3
    assert visual["confidence"] > 0.5 and visual["signals"] == ["attached image", "scoped request"]
    document = recommend("codex", "Review this", "auto:cost", CATALOG, [{"kind": "pdf"}, {"kind": "audio"}])
    assert document["model"] == "gpt-5.3-codex-spark" and document["fallback"] is False
    assert recommend("codex", "Hello", "auto:intelligence", CATALOG)["model"] == "gpt-6-astra"
    with pytest.raises(ValueError):
        routing_policy("mystery")


def test_attachment_validation_stages_bounded_public_metadata(tmp_path):
    raw = [{"name": "../Screen shot.png", "mimeType": "image/png",
            "data": base64.b64encode(b"not-a-secret-image").decode()},
           {"name": "Screen shot.png", "mimeType": "image/png",
            "data": base64.b64encode(b"second").decode()}]
    decoded = decode_attachments(raw)
    public = public_attachments(decoded)
    assert [row["name"] for row in public] == ["Screen shot.png", "Screen shot-2.png"]
    assert all("data" not in row and len(row["digest"]) == 64 for row in public)
    stage_attachments(tmp_path, decoded)
    assert (tmp_path / public[0]["relativePath"]).read_bytes() == b"not-a-secret-image"
    with pytest.raises(ValueError):
        decode_attachments([{"name": "x.exe", "mimeType": "application/x-executable", "data": "YQ=="}])
    with pytest.raises(ValueError):
        decode_attachments([{"name": "x.png", "mimeType": "image/png", "data": "***"}])


def test_agent_route_and_image_attachment_reach_codex_without_storing_payload(tmp_path):
    project = tmp_path / "project"; project.mkdir()
    service = WorkspaceService(tmp_path / "data")
    workspace = service.open_project({"path": str(project)})
    seen = {}

    def execute(spec, values, *_args, **kwargs):
        seen["command"] = spec["command"]
        seen["prompt"] = Path(values["prompt_file"]).read_text()
        image = Path(spec["command"][spec["command"].index("--image") + 1])
        seen["image"] = image.read_bytes()
        kwargs["on_output"]("stdout", json.dumps({"type": "thread.started", "thread_id": "route-session"}) + "\n")
        kwargs["on_output"]("stdout", json.dumps({"type": "item.completed", "item": {"id": "m", "type": "agent_message", "text": "Seen"}}) + "\n")
        return ProcessResult("completed", 0, "", "", 0, .01)

    try:
        payload = {"workspaceId": workspace["id"], "agent": "codex", "task": "Audit the architecture",
                   "mode": "read-only", "modelSelection": {"model": "", "effort": "", "routing": "auto:intelligence"},
                   "attachments": [{"name": "diagram.png", "mimeType": "image/png",
                                    "data": base64.b64encode(b"image-bytes").decode()}]}
        with patch("harness_manager.workspaces.service.executable", return_value="/codex"), \
             patch.object(service.profiles, "models", return_value={"models": CATALOG, "codexSource": "test", "warning": ""}), \
             patch("harness_manager.workspaces.service.run_profile", side_effect=execute):
            run = wait_for_task(service, service.send_conversation(payload))
        assert run["model"] == "gpt-6-astra"
        assert run["routing"] == "auto:intelligence" and run["route"]["policy"] == "auto:intelligence"
        assert run["attachments"][0]["name"] == "diagram.png"
        assert "data" not in json.dumps(run)
        assert seen["image"] == b"image-bytes"
        assert "diagram.png (image, image/png" in seen["prompt"]
        assert "sha256:" in seen["prompt"]
    finally:
        service.close()


def test_pdf_audio_and_video_are_staged_in_the_agent_manifest(tmp_path):
    project = tmp_path / "project"; project.mkdir()
    service = WorkspaceService(tmp_path / "data")
    workspace = service.open_project({"path": str(project)})
    seen = {}

    def execute(spec, values, *_args, **kwargs):
        seen["command"] = spec["command"]
        seen["prompt"] = Path(values["prompt_file"]).read_text()
        kwargs["on_output"]("stdout", json.dumps({"type": "thread.started", "thread_id": "media-session"}) + "\n")
        kwargs["on_output"]("stdout", json.dumps({"type": "item.completed", "item": {"id": "m", "type": "agent_message", "text": "Read"}}) + "\n")
        return ProcessResult("completed", 0, "", "", 0, .01)

    try:
        attachments = [
            {"name": "brief.pdf", "mimeType": "application/pdf", "data": base64.b64encode(b"pdf").decode()},
            {"name": "meeting.m4a", "mimeType": "audio/mp4", "data": base64.b64encode(b"audio").decode()},
            {"name": "demo.mov", "mimeType": "video/quicktime", "data": base64.b64encode(b"video").decode()},
        ]
        payload = {"workspaceId": workspace["id"], "agent": "codex", "task": "Inspect the attached material",
                   "mode": "read-only", "modelSelection": {"model": "gpt-5.6-luna", "effort": "low", "routing": "fixed"},
                   "attachments": attachments}
        with patch("harness_manager.workspaces.service.executable", return_value="/codex"), \
             patch("harness_manager.workspaces.service.run_profile", side_effect=execute):
            run = wait_for_task(service, service.send_conversation(payload))
        assert [item["kind"] for item in run["attachments"]] == ["pdf", "audio", "video"]
        assert all(item["relativePath"].startswith("ATTACHMENTS/") for item in run["attachments"])
        assert "brief.pdf (pdf, application/pdf" in seen["prompt"]
        assert "meeting.m4a (audio, audio/mp4" in seen["prompt"]
        assert "demo.mov (video, video/quicktime" in seen["prompt"]
        assert "--image" not in seen["command"]
    finally:
        service.close()
