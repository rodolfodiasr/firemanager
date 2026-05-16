"""Gera PDF de fatura usando WeasyPrint."""
from __future__ import annotations


def generate_invoice_pdf(invoice_data: dict) -> bytes:
    """
    invoice_data: {tenant_name, plan_name, amount_brl, period_start, period_end,
                   paid_at, invoice_number}
    Retorna bytes do PDF.
    """
    from weasyprint import HTML

    html = f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head><meta charset="UTF-8">
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; color: #1a1a1a; }}
        .header {{ display: flex; justify-content: space-between; margin-bottom: 40px; }}
        .logo {{ font-size: 24px; font-weight: bold; color: #2563eb; }}
        .invoice-title {{ font-size: 32px; font-weight: bold; color: #374151; }}
        .section {{ margin: 24px 0; }}
        .label {{ color: #6b7280; font-size: 12px; text-transform: uppercase; }}
        .value {{ font-size: 16px; margin-top: 4px; }}
        .amount {{ font-size: 36px; font-weight: bold; color: #2563eb; }}
        .footer {{ margin-top: 60px; padding-top: 20px; border-top: 1px solid #e5e7eb; color: #9ca3af; font-size: 12px; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #e5e7eb; }}
        th {{ background: #f9fafb; }}
    </style>
    </head>
    <body>
    <div class="header">
        <div class="logo">Eternity SecOps</div>
        <div class="invoice-title">FATURA</div>
    </div>
    <div class="section">
        <div class="label">Cliente</div>
        <div class="value">{invoice_data.get('tenant_name', '')}</div>
    </div>
    <div class="section">
        <div class="label">Número da Fatura</div>
        <div class="value">{invoice_data.get('invoice_number', '')}</div>
    </div>
    <table>
        <tr><th>Descrição</th><th>Período</th><th>Valor</th></tr>
        <tr>
            <td>{invoice_data.get('plan_name', '')} — Assinatura Mensal</td>
            <td>{invoice_data.get('period_start', '')} – {invoice_data.get('period_end', '')}</td>
            <td>R$ {invoice_data.get('amount_brl', 0):.2f}</td>
        </tr>
    </table>
    <div class="section" style="margin-top: 32px;">
        <div class="label">Total Pago</div>
        <div class="amount">R$ {invoice_data.get('amount_brl', 0):.2f}</div>
    </div>
    <div class="footer">
        Pago em {invoice_data.get('paid_at', '')} · Gerado automaticamente por Eternity SecOps
    </div>
    </body></html>
    """
    return HTML(string=html).write_pdf()
