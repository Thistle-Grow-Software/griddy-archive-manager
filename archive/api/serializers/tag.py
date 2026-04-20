from rest_framework import serializers

from archive.models import AssetTag, Tag


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ["id", "name"]


class AssetTagSerializer(serializers.ModelSerializer):
    asset = serializers.PrimaryKeyRelatedField(read_only=True)
    tag = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = AssetTag
        fields = ["id", "asset", "tag"]


class AssetTagWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetTag
        fields = ["asset", "tag"]
