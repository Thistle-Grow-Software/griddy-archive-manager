"""Serializers for the API key issuance/management endpoints."""

from __future__ import annotations

from rest_framework import serializers

from gam.accounts.models import APIKey, APIKeyEnvironment


class APIKeyListSerializer(serializers.ModelSerializer):
    """List/retrieve view — never exposes the plaintext token."""

    is_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = APIKey
        fields = (
            "id",
            "name",
            "environment",
            "key_prefix",
            "scopes",
            "created_at",
            "last_used_at",
            "expires_at",
            "revoked_at",
            "is_active",
        )
        read_only_fields = fields


class APIKeyCreateSerializer(serializers.ModelSerializer):
    """Issuance payload — accepts a name + optional scopes/expiry/env."""

    environment = serializers.ChoiceField(
        choices=APIKeyEnvironment.choices,
        default=APIKeyEnvironment.LIVE,
    )
    scopes = serializers.ListField(
        child=serializers.CharField(max_length=64),
        required=False,
        default=list,
    )
    expires_at = serializers.DateTimeField(required=False, allow_null=True)

    class Meta:
        model = APIKey
        fields = ("name", "environment", "scopes", "expires_at")


class APIKeyCreateResponseSerializer(serializers.Serializer):
    """Issuance response — returns the plaintext token exactly once."""

    api_key = APIKeyListSerializer()
    plaintext = serializers.CharField()
    warning = serializers.CharField()
