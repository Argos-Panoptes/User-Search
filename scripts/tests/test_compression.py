import json
import zlib
import sys
import time

# Sample data mimicking a user profile with group memberships
sample_data = {
    "service_id": "1234567890",
    "name": "John Doe",
    "about": "A very long description about John Doe who is a member of many groups and has a lot of metadata associated with his profile. "
    * 10,
    "group_memberships": [
        {"id": f"group_{i}", "name": f"Group Number {i}", "role": "member"}
        for i in range(100)
    ],
    "capabilities": "image, video, audio, text, sticker, location, contact, file, gif",
    "is_admin": False,
    "verified": "true",
}

json_str = json.dumps(sample_data)
json_bytes = json_str.encode("utf-8")
start_time = time.time()
compressed_data_1 = zlib.compress(json_bytes, level=1)
end_time = time.time()
print(f"Compression Time (Level 1): {end_time - start_time} seconds")
start_time = time.time()
compressed_data_9 = zlib.compress(json_bytes, level=9)
end_time = time.time()
print(f"Compression Time (Level 9): {end_time - start_time} seconds")

print(f"Original JSON Size: {len(json_bytes)} bytes")
print(f"Compressed Size: {len(compressed_data_1)} bytes")
print(f"Reduction: {100 - (len(compressed_data_1) / len(json_bytes) * 100)}%")

print(f"Original JSON Size: {len(json_bytes)} bytes")
print(f"Compressed Size: {len(compressed_data_9)} bytes")
print(f"Reduction: {100 - (len(compressed_data_9) / len(json_bytes) * 100)}%")
