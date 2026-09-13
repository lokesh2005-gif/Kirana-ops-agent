import os
import io
from datetime import date
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN

from app.db.database import SessionLocal
from app.services.analytics import (
    get_sales_summary, get_top_products, get_stock_health,
    get_gst_collected, get_daily_sales
)

REPORT_DIR = "artifacts/reports"
os.makedirs(REPORT_DIR, exist_ok=True)

BRAND_DARK = RGBColor(0x2E, 0x40, 0x57)
BRAND_LIGHT = RGBColor(0xF7, 0xF9, 0xFC)


def _add_title_slide(prs: Presentation, title: str, subtitle: str):
    layout = prs.slide_layouts[0]
    slide = prs.slides.add_slide(layout)
    slide.shapes.title.text = title
    slide.placeholders[1].text = subtitle
    slide.shapes.title.text_frame.paragraphs[0].runs[0].font.color.rgb = BRAND_DARK
    return slide


def _add_content_slide(prs: Presentation, title: str) -> object:
    layout = prs.slide_layouts[5]  # blank
    slide = prs.slides.add_slide(layout)
    txBox = slide.shapes.add_textbox(Inches(0.3), Inches(0.1), Inches(9), Inches(0.6))
    tf = txBox.text_frame
    p = tf.paragraphs[0]
    p.text = title
    run = p.runs[0]
    run.font.size = Pt(22)
    run.font.bold = True
    run.font.color.rgb = BRAND_DARK
    return slide


def _chart_image_stream(fig) -> io.BytesIO:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=150)
    plt.close(fig)
    buf.seek(0)
    return buf


def _add_image_to_slide(slide, img_stream, left=Inches(0.5), top=Inches(1.0), width=Inches(9)):
    slide.shapes.add_picture(img_stream, left, top, width=width)


def generate_sales_analysis_pptx(start_date: date, end_date: date) -> str:
    db = SessionLocal()
    try:
        summary = get_sales_summary(db, start_date, end_date)
        top_prods = get_top_products(db, start_date, end_date, n=5)
        stock = get_stock_health(db)
        gst = get_gst_collected(db, start_date, end_date)

        prs = Presentation()
        prs.slide_width = Inches(10)
        prs.slide_height = Inches(7.5)

        # Slide 1: Title
        _add_title_slide(prs, "Sales Analysis Report",
                         f"{start_date.strftime('%d %b %Y')} to {end_date.strftime('%d %b %Y')}")

        # Slide 2: Sales Summary
        slide = _add_content_slide(prs, "Sales Summary")
        lines = [
            f"Period: {start_date} to {end_date}",
            f"Total Bills: {summary['bill_count']}",
            f"Total Revenue: Rs.{summary['total_sales']:.2f}",
            f"CGST Collected: Rs.{gst['cgst']:.2f}",
            f"SGST Collected: Rs.{gst['sgst']:.2f}",
            f"Total GST: Rs.{gst['total']:.2f}",
        ]
        txBox = slide.shapes.add_textbox(Inches(0.5), Inches(1.0), Inches(9), Inches(5))
        tf = txBox.text_frame
        tf.word_wrap = True
        for i, line in enumerate(lines):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.text = line
            p.runs[0].font.size = Pt(16)

        # Slide 3: Top Products bar chart
        slide = _add_content_slide(prs, "Top Selling Products")
        if top_prods:
            names = [p["name"][:15] for p in top_prods]
            qtys = [p["qty"] for p in top_prods]
            fig, ax = plt.subplots(figsize=(8, 3.5))
            bars = ax.bar(names, qtys, color="#2E4057")
            ax.set_ylabel("Quantity Sold")
            ax.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))
            ax.bar_label(bars, fmt="%.1f")
            ax.set_title("Top Products by Quantity Sold")
            plt.xticks(rotation=15, ha="right")
            plt.tight_layout()
            _add_image_to_slide(slide, _chart_image_stream(fig))
        else:
            txBox = slide.shapes.add_textbox(Inches(1), Inches(2), Inches(8), Inches(2))
            txBox.text_frame.text = "No sales data in this period."

        # Slide 4: Stock Health
        slide = _add_content_slide(prs, "Stock Health")
        healthy = stock["healthy_products"]
        low = stock["low_stock_products"]
        total = stock["total_products"]
        if total > 0:
            fig, ax = plt.subplots(figsize=(4, 4))
            ax.pie([healthy, low], labels=["Healthy", "Low Stock"],
                   colors=["#4CAF50", "#F44336"], autopct="%1.0f%%", startangle=90)
            ax.set_title(f"Stock Health ({total} products)")
            _add_image_to_slide(slide, _chart_image_stream(fig), left=Inches(3), width=Inches(4))
        txBox = slide.shapes.add_textbox(Inches(0.5), Inches(5.8), Inches(9), Inches(1))
        txBox.text_frame.text = f"Total: {total}  |  Healthy: {healthy}  |  Low Stock: {low}"

        # Slide 5: GST Collected
        slide = _add_content_slide(prs, "GST Summary")
        if gst["total"] > 0:
            fig, ax = plt.subplots(figsize=(4, 3))
            ax.bar(["CGST", "SGST"], [gst["cgst"], gst["sgst"]], color=["#2196F3", "#FF9800"])
            ax.set_ylabel("Amount (Rs.)")
            ax.bar_label(ax.containers[0], fmt="Rs.%.2f")
            ax.set_title("GST Collected")
            _add_image_to_slide(slide, _chart_image_stream(fig), left=Inches(2.5), width=Inches(5))

        # Slide 6: Insights
        slide = _add_content_slide(prs, "Key Insights")
        insights = []
        if summary["bill_count"] > 0:
            avg = summary["total_sales"] / summary["bill_count"]
            insights.append(f"Average bill value: Rs.{avg:.2f}")
        if top_prods:
            insights.append(f"Best seller: {top_prods[0]['name']} ({top_prods[0]['qty']} units)")
        if low > 0:
            insights.append(f"Warning: {low} product(s) are at or below reorder level.")
        insights.append(f"GST liability for the period: Rs.{gst['total']:.2f}")
        if not insights:
            insights = ["No transactions recorded in this period."]

        txBox = slide.shapes.add_textbox(Inches(0.5), Inches(1.1), Inches(9), Inches(5))
        tf = txBox.text_frame
        tf.word_wrap = True
        for i, ins in enumerate(insights):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.text = f"• {ins}"
            p.runs[0].font.size = Pt(15)

        out_path = os.path.join(REPORT_DIR, f"sales_report_{start_date}_{end_date}.pptx")
        prs.save(out_path)
        return out_path
    finally:
        db.close()
