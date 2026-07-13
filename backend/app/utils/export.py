import io
from datetime import datetime
from typing import Literal

import pandas as pd
from fastapi.responses import StreamingResponse
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter

ExportFormat = Literal["csv", "excel"]


def generate_export(
    df: pd.DataFrame, report_name: str, export_format: ExportFormat = "excel"
) -> StreamingResponse:
    """Generate a StreamingResponse containing either a CSV or an Excel file.

    If Excel, applies basic formatting:
      - Bold headers
      - Auto-fit column widths
      - Freeze top row
    """
    date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{report_name}_{date_str}"

    if export_format == "csv":
        # CSV Injection protection
        for col in df.select_dtypes(include=['object']):
            df[col] = df[col].apply(
                lambda x: f"'{x}" if isinstance(x, str) and str(x).startswith(('=', '+', '-', '@')) else x
            )

        stream = io.StringIO()
        df.to_csv(stream, index=False)
        stream.seek(0)

        return StreamingResponse(
            iter([stream.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}.csv"},
        )

    # Excel formatting
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Report")
        worksheet = writer.sheets["Report"]

        # Freeze top row
        worksheet.freeze_panes = "A2"

        # Format headers and auto-fit columns
        for col_idx, col in enumerate(df.columns, 1):
            col_letter = get_column_letter(col_idx)

            # Header formatting
            header_cell = worksheet[f"{col_letter}1"]
            header_cell.font = Font(bold=True)
            header_cell.alignment = Alignment(horizontal="center")

            # Calculate max width for auto-fit
            max_len = len(str(col))
            for row in range(2, len(df) + 2):
                cell_val = worksheet[f"{col_letter}{row}"].value
                if cell_val is not None:
                    max_len = max(max_len, len(str(cell_val)))

            # Apply width with padding
            worksheet.column_dimensions[col_letter].width = max_len + 2

    output.seek(0)

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}.xlsx"},
    )
