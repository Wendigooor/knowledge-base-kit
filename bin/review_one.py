import urllib.request, json, sys

key = "sk-3ATgmddHMgg6ffGKdghETUDHm7cuYw4pmArm4oFqQRqtWhhPS908DfY3snFj21kO"
url = "https://opencode.ai/zen/go/v1/chat/completions"
headers = {"Content-Type": "application/json", "Authorization": f"Bearer {key}", "User-Agent": "Hermes-Agent/1.0"}

base = "/Users/iharzvezdzin/Documents/projects/knowledge-base-kit"

with open("/tmp/kbk-review-payload.txt") as f:
    prompt = f.read()

model_id = sys.argv[1]
label = sys.argv[2]

payload = {
    "model": model_id,
    "messages": [
        {"role": "system", "content": "You are a strict enterprise software architect. Review code critically, be specific with file:line references. Rate each area 1-10."},
        {"role": "user", "content": prompt}
    ],
    "max_tokens": 4096,
    "temperature": 0.3,
}
data = json.dumps(payload).encode()
req = urllib.request.Request(url, data=data, headers=headers)
resp = urllib.request.urlopen(req, timeout=600)
result = json.loads(resp.read())
msg = result["choices"][0]["message"]
content = msg.get("content", "")
reasoning = msg.get("reasoning", "")

output = f"# KBK v0.2 Review — {label}\n\n"
if reasoning:
    output += f"## Reasoning\n\n{reasoning}\n\n---\n\n"
output += content

safe_name = model_id.replace(".", "-")
path = f"/tmp/kbk-review-{safe_name}.md"
with open(path, "w") as f:
    f.write(output)
print(f"✅ {label}: {len(content)} chars -> {path}")
