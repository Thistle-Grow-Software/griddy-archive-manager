"""Response schema for the playback endpoint (TGF-360, ADR-0008).

The shape is intentionally minimal — three fields, no envelopes — so an
``openapi-ts``-generated client can call it without any post-processing. See
``docs/adr/0008-v1-video-delivery-r2-worker-hls.md`` for the rationale.
"""

from __future__ import annotations

from rest_framework import serializers


class PlaybackResponseSerializer(serializers.Serializer):
    """Schema mirrors the JSON contract documented in ADR-0008.

    Only ``hls`` is currently emitted for ``type``; future delivery modes
    (e.g. ``dash``, ``download``) would extend that enum without changing the
    rest of the response.
    """

    type = serializers.ChoiceField(choices=[("hls", "HLS")])
    url = serializers.URLField(
        help_text=(
            "Absolute URL to the master HLS manifest on the configured video "
            "origin, including the short-lived playback token as the ``t`` "
            "query parameter."
        ),
    )
    expires_at = serializers.DateTimeField(
        help_text="UTC ISO-8601 timestamp at which the embedded token expires.",
    )
