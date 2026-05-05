from fpdf import FPDF
import datetime
import os


class InvoiceGenerator:
    def __init__(self, output_dir="invoices"):
        self.output_dir = output_dir
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

    def generate_invoice(self, user_name, product_name, price_stars, purchase_id):
        """Muvaffaqiyatli to'lov uchun PDF hisob-faktura yaratish."""
        pdf = FPDF()
        pdf.add_page()

        # Sarlavha
        pdf.set_font("Arial", "B", 20)
        pdf.cell(0, 10, "INVOICE / HISOB-FAKTURA", ln=True, align="C")
        pdf.ln(10)

        # Kompaniya ma'lumotlari
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 10, "Provider: JonBranding Agency", ln=True)
        pdf.set_font("Arial", "", 10)
        pdf.cell(0, 5, "Website: https://jonbranding.uz", ln=True)
        pdf.cell(
            0, 5, f"Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}", ln=True
        )
        pdf.cell(0, 5, f"Invoice #: ST-{purchase_id}", ln=True)
        pdf.ln(10)

        # Mijoz ma'lumotlari
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 10, "Customer / Mijoz:", ln=True)
        pdf.set_font("Arial", "", 10)
        pdf.cell(0, 5, f"Name: {user_name}", ln=True)
        pdf.ln(10)

        # Jadval boshi
        pdf.set_fill_color(240, 240, 240)
        pdf.set_font("Arial", "B", 10)
        pdf.cell(140, 10, "Product / Mahsulot", 1, 0, "L", True)
        pdf.cell(50, 10, "Price (Stars)", 1, 1, "C", True)

        # Jadval tanasi
        pdf.set_font("Arial", "", 10)
        pdf.cell(140, 10, product_name, 1, 0, "L")
        pdf.cell(50, 10, str(price_stars), 1, 1, "C")

        # Jami
        pdf.ln(5)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(140, 10, "TOTAL / JAMI:", 0, 0, "R")
        pdf.cell(50, 10, f"{price_stars} Stars", 0, 1, "C")

        # Footer
        pdf.ln(20)
        pdf.set_font("Arial", "I", 8)
        pdf.cell(
            0,
            10,
            "JonBranding Assistant Bot orqali to'langan. Rahmat!",
            ln=True,
            align="C",
        )

        file_path = os.path.join(self.output_dir, f"invoice_{purchase_id}.pdf")
        pdf.output(file_path)
        return file_path


if __name__ == "__main__":
    # Test
    gen = InvoiceGenerator()
    path = gen.generate_invoice("Baxtiyorjon", "Logo Design Kit", 50, "9999")
    print(f"Generated: {path}")
