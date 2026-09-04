"""
PIP Memory layer - the user's picture (schema.sql's identity_avatar table).

Its own module rather than more of profile_store, which is already the largest
file in the memory layer, and because nothing here is a memory: an avatar is
not observed, inferred, confirmed, decayed or contradicted. It is a file
somebody chose, and every function that touches memory would have to make an
exception for it.

WHY THE FORMAT IS DETECTED AND NOT ACCEPTED
-------------------------------------------
The bytes are served back to the application with a Content-Type taken from
what is stored here, so whatever this records is what a renderer will be told
to treat the file as. Believing the client's declared type would mean an
upload could name its own Content-Type for bytes the server never looked at -
which is how a stored file becomes a stored script somewhere down the line.

So the type comes from the first few bytes, the upload is refused when they
are not one of two known image headers, and the client's claim is not read at
all. This is also, incidentally, the check that catches somebody selecting a
PDF: the answer is the same either way, because "this is not an image" is the
only thing worth saying about it.
"""

from typing import Any, Optional

from backend.core.types import now_utc

# 2 MB. The application downscales before uploading and sends something closer
# to 40 KB, so this is not the working limit - it is the backstop for a client
# that did not, or is not this one. Big enough that no reasonable picture is
# refused, small enough that the encrypted database does not quietly become a
# photo library.
MAX_BYTES = 2 * 1024 * 1024

# The two formats worth accepting: one lossless, one for photographs, both
# decodable by Flutter without a plugin. Identified by header rather than by
# extension or declared type - see the module docstring.
_MAGIC = (
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
)


class InvalidImageError(ValueError):
    """The bytes are not an image PIP will store, or there are too many."""


def detect_media_type(image: bytes) -> str:
    """
    The media type these bytes actually are.

    Raises rather than returning None, because every caller would otherwise
    have to turn None into the same refusal - and a silent fallback to
    'application/octet-stream' would store an unknown file under a name that
    makes it look known.
    """
    for magic, media_type in _MAGIC:
        if image.startswith(magic):
            return media_type
    raise InvalidImageError("That file is not a PNG or JPEG image.")


def set_avatar(conn, image: bytes) -> str:
    """
    Store *image* as the profile picture, replacing any existing one.

    Returns the detected media type, so the caller can answer with what was
    actually stored rather than what it was handed.
    """
    if not image:
        raise InvalidImageError("That file is empty.")
    if len(image) > MAX_BYTES:
        raise InvalidImageError(
            f"That image is {len(image) // 1024} KB. The limit is {MAX_BYTES // 1024} KB."
        )

    media_type = detect_media_type(image)

    conn.execute(
        "INSERT INTO identity_avatar (id, image, media_type, byte_size, updated_at) "
        "VALUES (1, ?, ?, ?, ?) "
        "ON CONFLICT(id) DO UPDATE SET "
        "image = excluded.image, media_type = excluded.media_type, "
        "byte_size = excluded.byte_size, updated_at = excluded.updated_at",
        (image, media_type, len(image), now_utc()),
    )
    conn.commit()
    return media_type


def get_avatar(conn) -> Optional[dict[str, Any]]:
    """The stored picture, or None. Returns the bytes; callers that only want
    to know whether one exists should use has_avatar()."""
    row = conn.execute(
        "SELECT image, media_type, byte_size, updated_at FROM identity_avatar WHERE id = 1"
    ).fetchone()
    return dict(row) if row else None


def has_avatar(conn) -> bool:
    """
    Whether there is a picture, without reading it.

    Separate from get_avatar because the common question is "should the app
    ask for the image" and answering it by loading up to two megabytes out of
    an encrypted database - to then throw them away - is the kind of thing that
    is only cheap while the picture is small.
    """
    return conn.execute("SELECT 1 FROM identity_avatar WHERE id = 1").fetchone() is not None


def clear_avatar(conn) -> bool:
    """Remove the picture. Returns whether there was one."""
    cursor = conn.execute("DELETE FROM identity_avatar WHERE id = 1")
    conn.commit()
    return cursor.rowcount > 0
