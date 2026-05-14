import urllib.request, json, sys

key = "sk-3ATgmddHMgg6ffGKdghETUDHm7cuYw4pmArm4oFqQRqtWhhPS908DfY3snFj21kO"
url = "https://opencode.ai/zen/go/v1/chat/completions"
headers = {"Content-Type": "application/json", "Authorization": f"Bearer {key}", "User-Agent": "Hermes-Agent/1.0"}

with open("/Users/iharzvezdzin/Downloads/localmaxxing-article.md") as f:
    article = f.read()

model_id = sys.argv[1]
label = sys.argv[2]

prompt = f"""Ты — редактор технического блога. Оцени и примизируй статью.

## Контекст

Это пост для LinkedIn/техблога от инженера, который пишет в стиле: русский, технический, короткие абзацы, без воды, с сарказмом, метафорами и конкретными цифрами. Аудитория — senior разработчики, техлиды, ML-инженеры. Цель — показать экспертизу и собрать обратную связь.

## Требования к стилю (оригинал)
- Русский язык, английские tech-термины
- Предложения 10-20 слов
- Абзацы 2-5 предложений
- Конкретные числа
- Разделители «---» между секциями
- Без corporate tone

## Статья

{article[:12000]}

## Задачи ревью
1. Факты — всё ли корректно?
2. Структура — логичная?
3. Стиль — соответствует голосу автора?
4. Дырки — чего не хватает?
5. Улучшения — что конкретно изменить (с примерами)?

Вердикт: approve/revise/reject."""

payload = {
    "model": model_id,
    "messages": [
        {"role": "system", "content": "Ты — строгий редактор технического блога. Пиши на русском. Оценивай критично, конкретно, с примерами."},
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

output = f"# Review: {label}\n\n"
if reasoning:
    output += f"## Reasoning\n\n{reasoning}\n\n---\n\n"
output += content

safe = model_id.replace(".", "-")
path = f"/tmp/localmaxxing-review-{safe}.md"
with open(path, "w") as f:
    f.write(output)
print(f"✅ {label}: {len(content)} chars -> {path}")
