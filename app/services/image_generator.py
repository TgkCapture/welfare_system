# app/services/image_generator.py
"""
Image generation service.

Produces PNG images from contribution data using matplotlib.

Two image types:
  paid_members  — table of contributors with financial summary header
  chart         — horizontal bar chart of top contributors

All rendering uses the non-interactive 'Agg' backend so this is safe
in a WSGI/threaded context with no display attached.
"""
import logging
import warnings
from io import BytesIO

import matplotlib
import matplotlib.pyplot as plt
import pandas as pd

matplotlib.use('Agg')   # Must be set before any pyplot import

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Colour palette — change here to re-theme all generated images
# ---------------------------------------------------------------------------
_BLUE       = '#2563eb'
_BLUE_LIGHT = '#dbeafe'
_SLATE_100  = '#f1f5f9'
_SLATE_800  = '#1e293b'
_SLATE_500  = '#334155'
_WHITE      = '#ffffff'
_BG         = '#f8fafc'


class ImageGenerator:
    """Generate PNG images from parsed contribution data."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @classmethod
    def generate_report_image(
        cls,
        data: dict,
        image_type: str = 'paid_members',
    ) -> BytesIO | None:
        """Safe wrapper — sets Agg backend, suppresses layout warnings.

        Args:
            data:       Dict from ExcelParser (or session report_data).
            image_type: ``'paid_members'`` or ``'chart'``.

        Returns:
            BytesIO PNG buffer, or None on failure.
        """
        plt.switch_backend('Agg')

        with warnings.catch_warnings():
            warnings.filterwarnings('ignore', category=UserWarning)

            if image_type == 'paid_members':
                return cls.generate_paid_members_image(data)
            if image_type == 'chart':
                return cls.generate_contribution_chart(data)

            logger.error(f"Unknown image_type: '{image_type}'")
            return None

    @staticmethod
    def generate_paid_members_image(data: dict) -> BytesIO | None:
        """Render a two-section PNG: financial summary + paid-members table.

        Returns None if there are no paid members or on any render error.
        """
        plt.switch_backend('Agg')

        try:
            df, month_col, name_col = ImageGenerator._extract_df(data)
            if df is None:
                return None

            paid_df = df[df[month_col].notna() & (df[month_col] > 0)]
            if paid_df.empty:
                logger.info("No paid members — skipping image generation")
                return None

            # ── Layout ────────────────────────────────────────────────
            row_h      = 0.38         
            summary_h  = 3.0          
            members_h  = max(1.5, len(paid_df) * row_h)
            fig_h      = summary_h + members_h + 0.8   # 0.8 for suptitle

            fig = plt.figure(figsize=(10, fig_h), dpi=150, facecolor=_BG)
            gs  = fig.add_gridspec(
                2, 1,
                height_ratios=[summary_h, members_h],
                hspace=0.4,
            )

            # ── Summary panel ─────────────────────────────────────────
            ax_s = fig.add_subplot(gs[0])
            ax_s.axis('off')

            summary_rows = ImageGenerator._build_summary_rows(data)
            s_table = ax_s.table(
                cellText=summary_rows,
                colWidths=[0.42, 0.58],
                cellLoc='left',
                loc='center',
                edges='open',
            )
            s_table.auto_set_font_size(False)
            s_table.set_fontsize(10)
            for i, (label, value) in enumerate(summary_rows):
                s_table._cells[(i, 0)].set_facecolor(_SLATE_100)
                s_table._cells[(i, 0)].set_text_props(
                    fontweight='bold', color=_SLATE_500
                )
                cell = s_table._cells[(i, 1)]
                cell.set_facecolor(_WHITE)
                if 'MWK' in value:
                    cell.set_text_props(fontweight='bold', color=_BLUE)
                elif value.replace(',', '').isdigit():
                    cell.set_text_props(fontweight='bold', color='#059669')
            s_table.scale(1, 1.8)

            # ── Members table ─────────────────────────────────────────
            ax_m = fig.add_subplot(gs[1])
            ax_m.axis('off')

            member_rows = []
            for _, row in paid_df.iterrows():
                try:
                    amt = f"MWK {float(row[month_col]):,.2f}"
                except (ValueError, TypeError):
                    amt = str(row[month_col])
                member_rows.append([str(row[name_col]), amt])

            if not member_rows:
                plt.close(fig)
                return None

            table_data = [['Member Name', 'Amount']] + member_rows
            m_table = ax_m.table(
                cellText=table_data,
                colWidths=[0.62, 0.38],
                cellLoc='left',
                loc='center',
            )
            m_table.auto_set_font_size(False)
            m_table.set_fontsize(10)

            # Header row styling
            for col in range(2):
                hc = m_table._cells[(0, col)]
                hc.set_facecolor(_BLUE)
                hc.set_text_props(color=_WHITE, fontweight='bold', fontsize=11)

            # Alternating row colours + right-align amounts
            for i in range(1, len(table_data)):
                bg = _SLATE_100 if i % 2 == 0 else _WHITE
                for col in range(2):
                    c = m_table._cells[(i, col)]
                    c.set_facecolor(bg)
                    if col == 1:
                        c.set_text_props(ha='right')
            m_table.scale(1, 1.5)

            # ── Title & save ──────────────────────────────────────────
            fig.suptitle(
                f"Paid Members — {data.get('month', '')} {data.get('year', '')}",
                fontsize=13, fontweight='bold',
                color=_SLATE_800, y=0.99,
            )

            buf = BytesIO()
            plt.savefig(
                buf, format='png', dpi=150,
                bbox_inches='tight', pad_inches=0.4,
                facecolor=fig.get_facecolor(),
            )
            buf.seek(0)
            logger.info(
                f"Generated paid-members image ({len(member_rows)} rows)"
            )
            return buf

        except Exception as e:
            logger.error(f"Error generating paid-members image: {e}", exc_info=True)
            return None
        finally:
            plt.close('all')

    @staticmethod
    def generate_contribution_chart(data: dict) -> BytesIO | None:
        """Render a horizontal bar chart of top contributors (max 15).

        Returns None if there is no data or on any render error.
        """
        plt.switch_backend('Agg')

        try:
            df, month_col, name_col = ImageGenerator._extract_df(data)
            if df is None:
                return None

            paid_df = (
                df[df[month_col].notna() & (df[month_col] > 0)]
                .sort_values(by=month_col, ascending=False)
                .head(15)
            )
            if paid_df.empty:
                return None

            n   = len(paid_df)
            fig, ax = plt.subplots(figsize=(12, max(4, n * 0.45)), dpi=150)
            fig.patch.set_facecolor(_BG)
            ax.set_facecolor(_BG)

            bars = ax.barh(
                range(n),
                paid_df[month_col].values,
                color=_BLUE, edgecolor='#1d4ed8', linewidth=0.5,
            )
            ax.set_yticks(range(n))
            ax.set_yticklabels(paid_df[name_col].values, fontsize=9)
            ax.invert_yaxis()

            # Value labels
            for bar, val in zip(bars, paid_df[month_col].values):
                w = bar.get_width()
                ax.text(
                    w * 1.01, bar.get_y() + bar.get_height() / 2,
                    f'MWK {val:,.0f}',
                    va='center', fontsize=8, fontweight='bold',
                )

            ax.xaxis.grid(True, linestyle='--', alpha=0.5)
            ax.set_axisbelow(True)
            ax.set_xlabel('Contribution (MWK)', fontweight='bold')
            ax.set_title(
                f"Top {n} Contributors — "
                f"{data.get('month', '')} {data.get('year', '')}",
                fontsize=12, fontweight='bold', pad=15,
            )

            plt.tight_layout()

            buf = BytesIO()
            plt.savefig(buf, format='png', dpi=150, bbox_inches='tight',
                        pad_inches=0.3, facecolor=_BG)
            buf.seek(0)
            logger.info(f"Generated contribution chart ({n} bars)")
            return buf

        except Exception as e:
            logger.error(f"Error generating contribution chart: {e}", exc_info=True)
            return None
        finally:
            plt.close('all')

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_df(data: dict):
        """Validate and return (df, month_col, name_col) or (None, …)."""
        month_col = data.get('month_col')
        name_col  = data.get('name_col')

        if not month_col or not name_col:
            logger.error("Missing 'month_col' or 'name_col' in data dict")
            return None, month_col, name_col

        raw = data.get('data')
        df  = raw if isinstance(raw, pd.DataFrame) else pd.DataFrame(raw or [])

        if df.empty:
            logger.info("Empty DataFrame — nothing to render")
            return None, month_col, name_col

        # Ensure amount column is numeric
        df[month_col] = pd.to_numeric(df[month_col], errors='coerce')
        return df, month_col, name_col

    @staticmethod
    def _build_summary_rows(data: dict) -> list:
        """Build the [[label, value], …] list for the summary table."""
        rows = [
            ['Report Period:', f"{data.get('month', 'N/A')} {data.get('year', 'N/A')}"],
            ['Total Contributions:', f"MWK {float(data.get('total_contributions', 0)):,.2f}"],
            ['Contributors:',        str(int(data.get('num_contributors', 0)))],
            ['Defaulters:',          str(int(data.get('num_missing', 0)))],
        ]

        dispensed = data.get('money_dispensed')
        if dispensed is not None:
            try:
                rows.append(['Money Dispensed:', f"MWK {float(dispensed):,.2f}"])
            except (ValueError, TypeError):
                rows.append(['Money Dispensed:', str(dispensed)])

        balance = data.get('total_book_balance')
        if balance is not None:
            try:
                rows.append(['Total Book Balance:', f"MWK {float(balance):,.2f}"])
            except (ValueError, TypeError):
                rows.append(['Total Book Balance:', str(balance)])

        return rows