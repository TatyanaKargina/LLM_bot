# test_gemini.py

from gemini import revise_text_with_chatgpt

if __name__ == "__main__":
    raw = "Это текст, который нужно переписать."
    comment = "Сделай его более профессиональным и структурированным."
    source = "Test Channel"

    revised = revise_text_with_chatgpt(raw, comment, source)
    print("\n🔄 Доработанный текст:")
    print(revised)
