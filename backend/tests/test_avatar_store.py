"""
The profile picture: stored inside the encrypted database, and typed by what
the bytes are rather than by what the upload said they were.

The images here are real PNG and JPEG files built byte by byte rather than
headers with junk behind them. A test that only ever feeds the detector its
own magic constants proves the constants match themselves.
"""

import sqlite3
import struct
import zlib

import pytest
from fastapi.testclient import TestClient

from backend.api import server
from backend.core import auth
from backend.memory import avatar_store
from backend.memory.profile_store import initialize_schema


def tiny_png() -> bytes:
    """A genuine 1x1 opaque PNG, assembled from its actual chunks."""
    def chunk(kind: bytes, body: bytes) -> bytes:
        return (
            struct.pack(">I", len(body))
            + kind
            + body
            + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)  # 1x1, 8-bit truecolour
    raw = b"\x00\xff\x00\x00"  # one filter byte, one red pixel
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


def tiny_jpeg() -> bytes:
    """Enough of a JPEG to be one: SOI, an APP0/JFIF header, and EOI."""
    return (
        b"\xff\xd8\xff\xe0"
        + struct.pack(">H", 16)
        + b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
        + b"\xff\xd9"
    )


@pytest.fixture
def conn():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    initialize_schema(connection)
    yield connection
    connection.close()


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PIP_DB_PATH", str(tmp_path / "pip.db"))
    token = auth.get_or_create_token(tmp_path / "api_token.txt")
    monkeypatch.setenv("PIP_TOKEN_PATH", str(tmp_path / "api_token.txt"))
    return TestClient(server.app), {"Authorization": f"Bearer {token}"}


# --- what the bytes are -----------------------------------------------------


def test_the_format_is_read_from_the_bytes(conn):
    assert avatar_store.detect_media_type(tiny_png()) == "image/png"
    assert avatar_store.detect_media_type(tiny_jpeg()) == "image/jpeg"


def test_anything_else_is_refused(conn):
    """
    The stored media_type is what a renderer is later told to treat the file
    as, so believing an upload's own claim would let it name the type for
    bytes nobody looked at.
    """
    with pytest.raises(avatar_store.InvalidImageError):
        avatar_store.detect_media_type(b"%PDF-1.7 not an image")
    with pytest.raises(avatar_store.InvalidImageError):
        avatar_store.detect_media_type(b"<svg xmlns='http://www.w3.org/2000/svg'/>")
    with pytest.raises(avatar_store.InvalidImageError):
        avatar_store.detect_media_type(b"")


def test_a_png_extension_does_not_make_something_a_png(conn):
    """The filename never reaches the detector, which is the point."""
    with pytest.raises(avatar_store.InvalidImageError):
        avatar_store.set_avatar(conn, b"MZ\x90\x00 this is an executable")


# --- storing ---------------------------------------------------------------


def test_a_picture_round_trips(conn):
    image = tiny_png()
    assert avatar_store.set_avatar(conn, image) == "image/png"

    stored = avatar_store.get_avatar(conn)
    assert stored["image"] == image
    assert stored["media_type"] == "image/png"
    assert stored["byte_size"] == len(image)


def test_setting_a_second_picture_replaces_the_first(conn):
    """Singleton, like the identity row it belongs to - one profile per
    database, and switching profiles means a different database."""
    avatar_store.set_avatar(conn, tiny_png())
    avatar_store.set_avatar(conn, tiny_jpeg())

    assert conn.execute("SELECT COUNT(*) FROM identity_avatar").fetchone()[0] == 1
    assert avatar_store.get_avatar(conn)["media_type"] == "image/jpeg"


def test_asking_whether_there_is_one_does_not_read_it(conn):
    """
    has_avatar exists so the common question does not pull up to two megabytes
    out of an encrypted database to then throw them away.
    """
    assert avatar_store.has_avatar(conn) is False
    avatar_store.set_avatar(conn, tiny_png())
    assert avatar_store.has_avatar(conn) is True


def test_an_oversized_image_is_refused_with_its_size(conn):
    too_big = tiny_png() + b"\x00" * avatar_store.MAX_BYTES

    with pytest.raises(avatar_store.InvalidImageError, match="KB"):
        avatar_store.set_avatar(conn, too_big)

    assert avatar_store.has_avatar(conn) is False


def test_clearing_reports_whether_there_was_one(conn):
    assert avatar_store.clear_avatar(conn) is False
    avatar_store.set_avatar(conn, tiny_png())
    assert avatar_store.clear_avatar(conn) is True
    assert avatar_store.get_avatar(conn) is None


# --- over HTTP --------------------------------------------------------------


def test_upload_then_fetch_returns_the_same_bytes(client):
    api, headers = client
    image = tiny_png()

    posted = api.post(
        "/api/v1/profile/picture",
        headers=headers,
        files={"file": ("me.png", image, "image/png")},
    )
    assert posted.status_code == 200
    assert posted.json()["media_type"] == "image/png"

    fetched = api.get("/api/v1/profile/picture", headers=headers)
    assert fetched.status_code == 200
    assert fetched.content == image
    assert fetched.headers["content-type"] == "image/png"


def test_the_served_type_comes_from_the_bytes_not_the_upload(client):
    """
    A JPEG announced as a PNG is served as a JPEG. The declared Content-Type is
    never read - it is how a stored file becomes a stored script somewhere
    downstream.
    """
    api, headers = client

    api.post(
        "/api/v1/profile/picture",
        headers=headers,
        files={"file": ("lying.png", tiny_jpeg(), "image/png")},
    )

    fetched = api.get("/api/v1/profile/picture", headers=headers)
    assert fetched.headers["content-type"] == "image/jpeg"


def test_no_picture_is_a_404_not_an_empty_image(client):
    """"There is no picture" is a real answer, and the app draws initials for
    it. A 200 carrying nothing would be a broken image instead."""
    api, headers = client
    assert api.get("/api/v1/profile/picture", headers=headers).status_code == 404


def test_a_file_that_is_not_an_image_is_refused_with_a_sentence(client):
    api, headers = client

    response = api.post(
        "/api/v1/profile/picture",
        headers=headers,
        files={"file": ("notes.pdf", b"%PDF-1.7 hello", "application/pdf")},
    )

    assert response.status_code == 422
    assert "not a PNG or JPEG" in response.json()["detail"]
    assert api.get("/api/v1/profile/picture", headers=headers).status_code == 404


def test_deleting_says_whether_there_was_one(client):
    api, headers = client

    assert api.delete("/api/v1/profile/picture", headers=headers).json()["status"] == "not_found"

    api.post(
        "/api/v1/profile/picture",
        headers=headers,
        files={"file": ("me.png", tiny_png(), "image/png")},
    )
    assert api.delete("/api/v1/profile/picture", headers=headers).json()["status"] == "deleted"
    assert api.get("/api/v1/profile/picture", headers=headers).status_code == 404


def test_the_picture_needs_the_token_like_everything_else(client):
    api, _ = client
    assert api.get("/api/v1/profile/picture").status_code == 401
    assert api.post("/api/v1/profile/picture", files={"file": ("a.png", tiny_png())}).status_code == 401
