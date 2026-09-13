import os
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.enums import TA_RIGHT, TA_CENTER

from app.db.database import SessionLocal
from app.db.models import Bill, BillItem, Product, Customer
from app.services.preferences import get_preference

INVOICE_DIR = "artifacts/invoices"
os.makedirs(INVOICE_DIR, exist_ok=True)

def generate_invoice_pdf(bill_id: int) -> str:
    db = SessionLocal()
    try:
        bill = db.query(Bill).filter(Bill.id == bill_id).first()
        if not bill:
            raise ValueError(f"Bill {bill_id} not found")
        if bill.status != "finalized":
            raise ValueError(f"Bill {bill_id} is not finalized")

        items = db.query(BillItem).filter(BillItem.bill_id == bill_id).all()
        customer = None
        if bill.customer_id:
            customer = db.query(Customer).filter(Customer.id == bill.customer_id).first()

        shop_name = get_preference(db, "shop_name", "My Kirana Store")
        gstin = get_preference(db, "gstin", "GSTIN: Not Set")
        shop_address = get_preference(db, "shop_address", "")

        file_path = os.path.join(INVOICE_DIR, f"invoice_{bill.bill_number}.pdf")
        doc = SimpleDocTemplate(file_path, pagesize=A4, rightMargin=15*mm, leftMargin=15*mm, topMargin=15*mm, bottomMargin=15*mm)
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle("title", parent=styles["Heading1"], alignment=TA_CENTER, fontSize=18)
        sub_style = ParagraphStyle("sub", parent=styles["Normal"], alignment=TA_CENTER, fontSize=10)
        right_style = ParagraphStyle("right", parent=styles["Normal"], alignment=TA_RIGHT)
        bold_style = ParagraphStyle("bold", parent=styles["Normal"], fontName="Helvetica-Bold")

        story = []
        story.append(Paragraph(shop_name, title_style))
        if shop_address:
            story.append(Paragraph(shop_address, sub_style))
        story.append(Paragraph(f"GSTIN: {gstin}", sub_style))
        story.append(Spacer(1, 6*mm))

        story.append(Paragraph("TAX INVOICE", ParagraphStyle("tax", parent=styles["Heading2"], alignment=TA_CENTER)))
        story.append(Spacer(1, 4*mm))

        meta_data = [
            [Paragraph(f"<b>Invoice No:</b> {bill.bill_number}", styles["Normal"]),
             Paragraph(f"<b>Date:</b> {bill.finalized_at.strftime('%d-%m-%Y') if bill.finalized_at else 'N/A'}", right_style)],
        ]
        if customer:
            meta_data.append([
                Paragraph(f"<b>Customer:</b> {customer.name} {('| Ph: ' + customer.phone) if customer.phone else ''}", styles["Normal"]),
                Paragraph(f"<b>Payment:</b> {bill.payment_mode or '-'} {('| Ref: ' + bill.payment_reference) if bill.payment_reference else ''}", right_style)
            ])

        meta_table = Table(meta_data, colWidths=[90*mm, 90*mm])
        meta_table.setStyle(TableStyle([('BOTTOMPADDING', (0,0), (-1,-1), 2*mm)]))
        story.append(meta_table)
        story.append(Spacer(1, 5*mm))

        # Line items table
        headers = ["#", "Product", "HSN", "Qty", "Unit Price", "Taxable", "GST%", "CGST", "SGST", "Total"]
        table_data = [headers]

        for i, item in enumerate(items, 1):
            prod = db.query(Product).filter(Product.id == item.product_id).first()
            table_data.append([
                str(i),
                prod.name if prod else "Unknown",
                prod.hsn_code if prod and prod.hsn_code else "-",
                f"{item.quantity} {prod.unit if prod else ''}",
                f"Rs.{item.unit_price:.2f}",
                f"Rs.{item.taxable_amount:.2f}",
                f"{item.gst_rate}%",
                f"Rs.{item.cgst_amount:.2f}",
                f"Rs.{item.sgst_amount:.2f}",
                f"Rs.{item.line_total:.2f}",
            ])

        col_widths = [8*mm, 38*mm, 16*mm, 14*mm, 18*mm, 18*mm, 10*mm, 14*mm, 14*mm, 18*mm]
        items_table = Table(table_data, colWidths=col_widths, repeatRows=1)
        items_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#2E4057")),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 8),
            ('GRID', (0,0), (-1,-1), 0.25, colors.grey),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#F7F9FC")]),
            ('ALIGN', (3,0), (-1,-1), 'RIGHT'),
            ('TOPPADDING', (0,0), (-1,-1), 2),
            ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ]))
        story.append(items_table)
        story.append(Spacer(1, 5*mm))

        # Totals block
        totals = [
            ["", "", "", "", "", "", "", "", "Subtotal:", f"Rs.{bill.subtotal:.2f}"],
            ["", "", "", "", "", "", "", "", "CGST:", f"Rs.{bill.cgst_total:.2f}"],
            ["", "", "", "", "", "", "", "", "SGST:", f"Rs.{bill.sgst_total:.2f}"],
            ["", "", "", "", "", "", "", "", "GRAND TOTAL:", f"Rs.{bill.total:.2f}"],
        ]
        totals_table = Table(totals, colWidths=col_widths)
        totals_table.setStyle(TableStyle([
            ('FONTNAME', (8,3), (9,3), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 8),
            ('ALIGN', (8,0), (9,-1), 'RIGHT'),
            ('LINEABOVE', (8,3), (9,3), 0.5, colors.black),
        ]))
        story.append(totals_table)
        story.append(Spacer(1, 8*mm))
        story.append(Paragraph("Thank you for your business!", sub_style))

        doc.build(story)
        return file_path
    finally:
        db.close()
