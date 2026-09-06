import json
import os
import urllib.request

token = os.environ["GH_TOKEN"]

print("=== GET /repos/.../pages ===")
req = urllib.request.Request(
    "https://api.github.com/repos/sturcjan-rgb/srsni-truth/pages",
    headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
)
try:
    with urllib.request.urlopen(req) as resp:
        print(resp.status)
        print(json.dumps(json.loads(resp.read()), indent=2))
except urllib.error.HTTPError as e:
    print(e.code, e.read().decode())

print()
print("=== GET live index.html (first 1500 chars) ===")
req2 = urllib.request.Request("https://sturcjan-rgb.github.io/srsni-truth/")
with urllib.request.urlopen(req2) as resp:
    print(resp.status, resp.headers.get("Last-Modified"), resp.headers.get("Age"))
    body = resp.read().decode(errors="replace")
    print(body[:1500])
