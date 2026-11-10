import pdfplumber

with pdfplumber.open("BSMMU.pdf") as pdf:
    for number, page in enumerate(pdf.pages, start=1):
        text = page.extract_text() or ""

        # ১) এই পেজ কি DHAKA-1 এর?
        rsm_ok = "DHAKA-1" in text
        in_hormon = False
        am_base = ""

        for line in text.split("\n"):
            line = line.strip()

            # AM Base লাইনটা মনে রাখো
            if "AM Base" in line and "Total" not in line:
                am_base = line

            # ২) HORMON শুরু
            if line == "HORMON":
                in_hormon = True
                continue

            # ৩) Group Total এলে HORMON শেষ
            if "Group Total" in line:
                in_hormon = False

            # ৪) প্রোডাক্ট সারি: ৬ অঙ্কের কোড দিয়ে শুরু
            if rsm_ok and in_hormon and line[:6].isdigit():
                print(number, "|", am_base, "|", line)