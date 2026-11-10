import pdfplumber
with pdfplumber .open("BSMMU.pdf") as pdf:
   print("Total Page: ", len(pdf.pages))
   print(pdf.pages[0].extract_text())