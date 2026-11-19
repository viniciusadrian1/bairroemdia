import re


def mask(text):
    """Redação defensiva complementar. Não equivale a anonimização universal/NER."""
    for pattern, marker in [
        (r'\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b','[CPF]'),
        (r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}','[EMAIL]'),
        (r'(?<!\d)(?:\+55\s*)?(?:\(?\d{2}\)?\s*)?\d{4,5}[-\s]?\d{4}(?!\d)','[TELEFONE]')]:
        text=re.sub(pattern,marker,text)
    return text
