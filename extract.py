import re
import pdfplumber

# প্রোডাক্ট সারির নকশা: ৬ অঙ্কের কোড, নাম, তারপর ১৪টা সংখ্যা
ROW = re.compile(r"^(\d{6})\s+([A-Za-z].*?)\s+((?:-?[\d,]+(?:\.\d+)?\s*){14})$")

group = ""

with pdfplumber.open("BSMMU.pdf") as pdf:
    for page_no, page in enumerate(pdf.pages, start=1):
        text = page.extract_text() or ""
        if "DHAKA-1" not in text:
            continue
        for line in text.split("\n"):
            line = line.strip()
            if line.startswith("Group "):
                group = line[6:].strip()
                continue
            if group != "HORMON":
                continue
            m = ROW.match(line)
            if m:
                code = m.group(1)
                name = m.group(2)
                numbers = [float(x.replace(",", "")) for x in m.group(3).split()]
                print(page_no, code, name, numbers[:7])