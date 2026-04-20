from rest_framework import serializers

from archive.models import VideoAsset


class VideoAssetListSerializer(serializers.ModelSerializer):
    game = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = VideoAsset
        fields = [
            "id",
            "game",
            "asset_type",
            "quality_tier",
            "file_size_bytes",
            "duration_seconds",
            "is_preferred",
            "created_at",
        ]


class VideoAssetDetailSerializer(serializers.ModelSerializer):
    game = serializers.PrimaryKeyRelatedField(read_only=True)
    acquisition = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = VideoAsset
        fields = [
            "id",
            "game",
            "acquisition",
            "asset_type",
            "file_path",
            "container",
            "video_codec",
            "audio_codec",
            "resolution_w",
            "resolution_h",
            "fps",
            "bitrate_kbps",
            "duration_seconds",
            "file_size_bytes",
            "language",
            "has_commercials",
            "quality_tier",
            "quality_notes",
            "is_preferred",
            "checksum_sha256",
            "created_at",
            "last_verified_at",
            "source_url",
            "bonus_data",
            "external_ids",
        ]


class VideoAssetWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = VideoAsset
        fields = [
            "game",
            "acquisition",
            "asset_type",
            "file_path",
            "container",
            "video_codec",
            "audio_codec",
            "resolution_w",
            "resolution_h",
            "fps",
            "bitrate_kbps",
            "duration_seconds",
            "file_size_bytes",
            "language",
            "has_commercials",
            "quality_tier",
            "quality_notes",
            "is_preferred",
            "checksum_sha256",
            "source_url",
            "bonus_data",
            "external_ids",
        ]
