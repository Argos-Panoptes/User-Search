import base64


def base64url_encode(data):
    """Encode bytes to base64url (URL-safe base64 without padding)."""
    encoded = base64.urlsafe_b64encode(data).decode("ascii")
    # Remove padding
    return encoded.rstrip("=")


def generate_signal_group_url(
    master_key_b64: str, invite_password_b64: str
) -> str | None:
    """
    Generate a Signal Group URL from master key and invite password.

    Args:
        master_key_b64: Base64-encoded master key (32 bytes when decoded)
        invite_password_b64: Base64-encoded invite password (16 bytes when decoded)

    Returns:
        Signal Group URL string or None if inputs are invalid
    """
    if not master_key_b64 or not invite_password_b64:
        return None

    try:
        # Decode base64 strings to bytes
        master_key_bytes = base64.b64decode(master_key_b64)
        password_bytes = base64.b64decode(invite_password_b64)

        # Verify lengths
        if len(master_key_bytes) != 32 or len(password_bytes) != 16:
            return None

        # Construct protobuf structure:
        # Bytes 0-3: [10, 52, 10, 32] - fixed header
        # Bytes 4-35: 32-byte master key
        # Bytes 36-37: [18, 16] - fixed header
        # Bytes 38-53: 16-byte password
        protobuf = bytearray(54)
        protobuf[0] = 10
        protobuf[1] = 52
        protobuf[2] = 10
        protobuf[3] = 32
        protobuf[4:36] = master_key_bytes
        protobuf[36] = 18
        protobuf[37] = 16
        protobuf[38:54] = password_bytes

        # Base64url encode the protobuf
        encoded = base64url_encode(bytes(protobuf))

        # Construct the URL
        return f"https://signal.group/#{encoded}"

    except Exception as e:
        print(f"Error generating URL: {e}")
        return None
