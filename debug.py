import pdfplumber

with pdfplumber.open("BSMMU.pdf") as pdf:
    for number, page in enumerate(pdf.pages, start=1):
        text = page.extract_text() or ""
        print("পেজ", number,
              "| DHAKA-1:", "DHAKA-1" in text,
              "| HORMON:", "HORMON" in text.upper())

        lines = text.split("\n")
        for i, line in enumerate(lines):
            if "HORMON" in line.upper():
                print("   HORMON লাইন:", repr(line))
                if i + 1 < len(lines):
                    print("   তার পরের লাইন:", repr(lines[i + 1]))