"""Email alert service.

Compiles stockout predictions and alerts into a clean HTML email and sends it
via SMTP.  Falls back to logging if SMTP is not configured.
"""

from __future__ import annotations

import logging
import smtplib
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List

from sqlalchemy.orm import Session

import config
from database import Alert, ProductVariant, StockoutPrediction

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def generate_daily_report(db: Session) -> Dict[str, Any]:
    """Compile all current predictions and alerts into a structured report dict."""
    predictions = (
        db.query(StockoutPrediction, ProductVariant)
        .join(ProductVariant, StockoutPrediction.variant_id == ProductVariant.id)
        .order_by(StockoutPrediction.days_until_stockout.asc().nullslast())
        .all()
    )

    alerts = (
        db.query(Alert, ProductVariant)
        .join(ProductVariant, Alert.variant_id == ProductVariant.id)
        .filter(Alert.is_read == False)  # noqa: E712
        .order_by(Alert.created_at.desc())
        .all()
    )

    stockout_warnings = []
    reorder_recs = []
    dead_items = []
    actions_today: List[str] = []

    for alert, variant in alerts:
        entry = {
            "sku": variant.sku,
            "size": variant.size,
            "color": variant.color,
            "product_name": variant.product.name if variant.product else "",
            "message": alert.message,
            "type": alert.type,
        }
        if alert.type == "stockout":
            stockout_warnings.append(entry)
            actions_today.append(f"Check stock for {variant.sku}")
        elif alert.type == "reorder":
            reorder_recs.append(entry)
            actions_today.append(f"Place order for {variant.sku}")
        elif alert.type == "dead_inventory":
            dead_items.append(entry)

    return {
        "date": date.today().isoformat(),
        "actions_today": actions_today,
        "stockout_warnings": stockout_warnings,
        "reorder_recommendations": reorder_recs,
        "dead_inventory": dead_items,
        "total_predictions": len(predictions),
        "critical_count": len(stockout_warnings),
    }


# ---------------------------------------------------------------------------
# HTML formatting
# ---------------------------------------------------------------------------

def format_email_html(report: Dict[str, Any]) -> str:
    """Render the daily report as a clean HTML email body."""
    actions_html = ""
    if report["actions_today"]:
        items = "".join(f"<li>{a}</li>" for a in report["actions_today"])
        actions_html = f"""
        <div style="background:#fef3c7;border-left:4px solid #f59e0b;padding:16px;margin-bottom:24px;border-radius:4px;">
            <h2 style="margin:0 0 8px;color:#92400e;font-size:18px;">Today's Actions</h2>
            <ul style="margin:0;padding-left:20px;color:#78350f;">{items}</ul>
        </div>"""

    def _alert_section(title: str, items: list, bg: str, border: str, title_color: str) -> str:
        if not items:
            return ""
        rows = "".join(
            f'<tr><td style="padding:8px;border-bottom:1px solid #e5e7eb;">{i["sku"]}</td>'
            f'<td style="padding:8px;border-bottom:1px solid #e5e7eb;">{i["product_name"]} ({i["size"]})</td>'
            f'<td style="padding:8px;border-bottom:1px solid #e5e7eb;">{i["message"]}</td></tr>'
            for i in items
        )
        return f"""
        <div style="margin-bottom:24px;">
            <h2 style="color:{title_color};font-size:18px;margin-bottom:8px;">{title} ({len(items)})</h2>
            <table style="width:100%;border-collapse:collapse;font-size:14px;">
                <thead><tr style="background:{bg};border-left:4px solid {border};">
                    <th style="text-align:left;padding:8px;">SKU</th>
                    <th style="text-align:left;padding:8px;">Product</th>
                    <th style="text-align:left;padding:8px;">Details</th>
                </tr></thead>
                <tbody>{rows}</tbody>
            </table>
        </div>"""

    stockout_html = _alert_section(
        "Stockout Warnings", report["stockout_warnings"],
        "#fee2e2", "#ef4444", "#991b1b",
    )
    reorder_html = _alert_section(
        "Reorder Recommendations", report["reorder_recommendations"],
        "#dbeafe", "#3b82f6", "#1e40af",
    )
    dead_html = _alert_section(
        "Dead Inventory", report["dead_inventory"],
        "#f3f4f6", "#9ca3af", "#374151",
    )

    html = f"""\
<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:#1f2937;max-width:700px;margin:0 auto;padding:24px;">
    <div style="border-bottom:2px solid #111827;padding-bottom:12px;margin-bottom:24px;">
        <h1 style="margin:0;font-size:24px;">Inventory Intelligence Report</h1>
        <p style="margin:4px 0 0;color:#6b7280;font-size:14px;">{report['date']}</p>
    </div>
    {actions_html}
    {stockout_html}
    {reorder_html}
    {dead_html}
    <div style="margin-top:32px;padding-top:16px;border-top:1px solid #e5e7eb;font-size:12px;color:#9ca3af;">
        Generated by Inventory AI &middot; Predictions based on {report['total_predictions']} tracked variants
    </div>
</body></html>"""
    return html


# ---------------------------------------------------------------------------
# Email sending
# ---------------------------------------------------------------------------

def send_alert_email(db: Session) -> bool:
    """Generate the daily report, format it, and send via SMTP.

    Returns True if sent successfully, False otherwise.
    Falls back to logging the report if SMTP is not configured.
    """
    report = generate_daily_report(db)
    html = format_email_html(report)

    # Check if there is anything worth sending
    if not report["actions_today"] and not report["stockout_warnings"] and not report["dead_inventory"]:
        logger.info("No alerts to send today — all inventory is healthy.")
        return False

    # If SMTP is not configured, log the report instead
    if not config.SMTP_HOST or not config.ALERT_EMAIL_TO:
        logger.warning(
            "SMTP not configured. Daily report (%d actions, %d critical) logged instead of emailed.",
            len(report["actions_today"]),
            report["critical_count"],
        )
        logger.info("Report summary: %s", {k: v for k, v in report.items() if k != "date"})
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Inventory Alert — {report['critical_count']} critical, {len(report['actions_today'])} actions ({report['date']})"
    msg["From"] = config.ALERT_EMAIL_FROM
    msg["To"] = config.ALERT_EMAIL_TO
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(config.SMTP_USER, config.SMTP_PASSWORD)
            server.send_message(msg)
        logger.info("Daily alert email sent to %s", config.ALERT_EMAIL_TO)
        return True
    except Exception:
        logger.exception("Failed to send alert email")
        return False
