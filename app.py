"""
أداة استخراج بيانات من المواقع باستخدام الذكاء الاصطناعي (Gemini)
تعمل كتطبيق ويب واحد (Streamlit) — يمكن نشره مجاناً واستخدامه من الهاتف.
"""

import json
import re

import requests
import streamlit as st
from bs4 import BeautifulSoup

# ---------- إعدادات الصفحة ----------
st.set_page_config(page_title="مستخرج البيانات الذكي", page_icon="🔎", layout="centered")

# ---------- دوال مساعدة ----------

def fetch_page_text(url: str, timeout: int = 15) -> str:
    """يجلب صفحة الويب وينظفها من الأكواد ويعيد نص القراءة فقط."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0 Safari/537.36"
        )
    }
    resp = requests.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "lxml")

    # إزالة العناصر غير المفيدة للتحليل
    for tag in soup(["script", "style", "noscript", "svg", "iframe"]):
        tag.decompose()

    text = soup.get_text(separator="\n")
    # تنظيف الأسطر الفارغة المتكررة
    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    cleaned = "\n".join(lines)
    return cleaned


def truncate_text(text: str, max_chars: int = 18000) -> str:
    """يقصّ النص الطويل حتى لا يتجاوز حد النموذج."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n\n... (تم اقتصاص باقي المحتوى لطوله) ..."


def build_prompt(instructions: str, page_content: str, url: str) -> str:
    return f"""أنت أداة استخراج بيانات دقيقة. لديك محتوى صفحة ويب، ولديك تعليمات من المستخدم
تخبرك بالضبط ما هي البيانات التي يريد استخراجها من هذا المحتوى.

رابط الصفحة: {url}

تعليمات المستخدم (السكريبت):
---
{instructions}
---

محتوى الصفحة (نص مستخرج من HTML):
---
{page_content}
---

المطلوب منك:
1. اقرأ تعليمات المستخدم جيداً وحدد بالضبط أي بيانات يريدها.
2. ابحث عنها داخل محتوى الصفحة أعلاه فقط، ولا تخترع بيانات غير موجودة.
3. إذا لم تجد بيانات مطابقة، أعد قائمة فارغة بدلاً من اختلاق معلومات.
4. أعد الناتج **بصيغة JSON فقط**، بدون أي شرح أو نص إضافي أو علامات ```.
5. صيغة الناتج يجب أن تكون:
{{
  "found": true أو false,
  "summary": "جملة قصيرة تشرح ماذا وجدت",
  "items": [ ... قائمة بالعناصر المستخرجة كأي شكل JSON مناسب للبيانات المطلوبة ... ]
}}
"""


def call_gemini(api_key: str, model_name: str, prompt: str) -> str:
    """يستدعي واجهة Gemini API عبر REST مباشرة (بدون مكتبات إضافية)."""
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model_name}:generateContent?key={api_key}"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "response_mime_type": "application/json",
        },
    }
    resp = requests.post(url, json=payload, timeout=60)
    if resp.status_code != 200:
        raise RuntimeError(f"خطأ من Gemini API ({resp.status_code}): {resp.text[:500]}")

    data = resp.json()
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        raise RuntimeError(f"استجابة غير متوقعة من النموذج: {json.dumps(data)[:500]}")


def extract_json(raw_text: str) -> dict:
    """يحاول استخراج JSON صالح من نص الرد حتى لو احتوى على زوائد."""
    raw_text = raw_text.strip()
    raw_text = re.sub(r"^```json\s*|\s*```$", "", raw_text, flags=re.MULTILINE)
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw_text, flags=re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise


# ---------- الشريط الجانبي: إعدادات ----------
with st.sidebar:
    st.header("⚙️ الإعدادات")
    api_key = st.text_input(
        "مفتاح Gemini API (مجاني)",
        type="password",
        help="احصل عليه مجاناً من https://aistudio.google.com/apikey",
    )
    model_name = st.selectbox(
        "النموذج",
        ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"],
        index=0,
    )
    st.markdown("---")
    st.caption("مفتاحك لا يُحفظ في أي مكان، يُستخدم فقط أثناء هذه الجلسة.")

# ---------- الواجهة الرئيسية ----------
st.title("🔎 مستخرج البيانات الذكي")
st.write("أدخل رابط الموقع + تعليمات نصية توضح ما تريد استخراجه، وسيقوم التطبيق بالباقي.")

url = st.text_input("رابط الموقع", placeholder="https://example.com/page")
instructions = st.text_area(
    "تعليمات الاستخراج (السكريبت)",
    placeholder="مثال: استخرج لي اسم كل منتج وسعره من هذه الصفحة",
    height=120,
)

run = st.button("🚀 تحليل الآن", use_container_width=True, type="primary")

if run:
    if not api_key:
        st.error("الرجاء إدخال مفتاح Gemini API في الشريط الجانبي أولاً.")
    elif not url or not instructions:
        st.error("الرجاء إدخال الرابط وتعليمات الاستخراج.")
    else:
        try:
            with st.spinner("جاري جلب محتوى الصفحة..."):
                page_text = fetch_page_text(url)
                page_text = truncate_text(page_text)

            if not page_text:
                st.warning("لم يتم العثور على محتوى نصي في هذه الصفحة.")
            else:
                with st.spinner("جاري التحليل بواسطة الذكاء الاصطناعي..."):
                    prompt = build_prompt(instructions, page_text, url)
                    raw_response = call_gemini(api_key, model_name, prompt)
                    result = extract_json(raw_response)

                st.success("تم التحليل بنجاح ✅")
                st.subheader("الملخص")
                st.write(result.get("summary", "لا يوجد ملخص"))

                items = result.get("items", [])
                st.subheader(f"البيانات المستخرجة ({len(items)} عنصر)")
                if items:
                    st.json(items)
                    st.download_button(
                        "⬇️ تحميل النتائج كـ JSON",
                        data=json.dumps(items, ensure_ascii=False, indent=2),
                        file_name="extracted_data.json",
                        mime="application/json",
                    )
                else:
                    st.info("لم يتم العثور على بيانات مطابقة للتعليمات.")

                with st.expander("عرض محتوى الصفحة الخام (للتشخيص)"):
                    st.text(page_text[:3000])

        except requests.exceptions.RequestException as e:
            st.error(f"تعذر الوصول إلى الرابط: {e}")
        except Exception as e:
            st.error(f"حدث خطأ أثناء التحليل: {e}")
