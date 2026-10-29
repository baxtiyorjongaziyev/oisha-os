with open('scripts/shared.js', 'r', encoding='utf-8') as f:
    text = f.read()

idx = text.find('async function e(a,i={})')
print(text[idx:idx+1000])
