# app/services/image_generator.py
import matplotlib.pyplot as plt
import pandas as pd
from io import BytesIO
import numpy as np
from flask import current_app
import logging

logger = logging.getLogger(__name__)

class ImageGenerator:
    """Utility class for generating images from data"""
    
    @staticmethod
    def generate_paid_members_image(data):
        """Generate PNG image of paid members with financial summary"""
        try:
            # Ensure data is properly formatted
            if not isinstance(data.get('data'), pd.DataFrame):
                data['data'] = pd.DataFrame(data['data'])
            
            # Check if we have month column
            month_col = data.get('month_col')
            name_col = data.get('name_col')
            
            if not month_col or not name_col:
                logger.error("Missing month_col or name_col in data")
                return None
            
            # Filter paid members (non-null in month column)
            df = data['data']
            paid_df = df[~df[month_col].isna()]
            
            if paid_df.empty:
                logger.info("No paid members found to generate image")
                return None
            
            # Calculate figure height based on number of rows
            base_height = 4  # For summary section
            row_height = 0.4  # Height per row of data
            fig_height = max(base_height, base_height + len(paid_df) * row_height)
            
            # Create figure with improved styling
            plt.style.use('default')
            fig = plt.figure(figsize=(10, fig_height), dpi=150)
            fig.patch.set_facecolor('#f8fafc')
            
            # Create grid layout
            gs = fig.add_gridspec(2, 1, 
                                 height_ratios=[1.5, len(paid_df) * row_height],
                                 hspace=0.3)
            
            # Financial Summary Section
            ax_summary = fig.add_subplot(gs[0])
            ax_summary.axis('off')
            
            # Prepare summary data
            summary_data = []
            
            # Report period
            summary_data.append(["Report Period:", f"{data.get('month', 'N/A')} {data.get('year', 'N/A')}"])
            
            # Financial metrics
            financial_metrics = [
                ("Total Contributions:", data.get('total_contributions', 0)),
                ("Contributors:", data.get('num_contributors', 0)),
                ("Defaulters:", data.get('num_missing', 0)),
            ]
            
            for label, value in financial_metrics:
                if isinstance(value, (int, float)):
                    if "MWK" in label or "K" in label or "Total" in label:
                        formatted_value = f"MWK {float(value):,.2f}"
                    else:
                        formatted_value = f"{int(value):,}"
                    summary_data.append([label, formatted_value])
                else:
                    summary_data.append([label, str(value)])
            
            # Additional financial info if available
            money_dispensed = data.get('money_dispensed')
            if money_dispensed is not None:
                try:
                    formatted = f"MWK {float(money_dispensed):,.2f}"
                    summary_data.append(["Money Dispensed:", formatted])
                except (ValueError, TypeError):
                    summary_data.append(["Money Dispensed:", str(money_dispensed)])
            
            total_book_balance = data.get('total_book_balance')
            if total_book_balance is not None:
                try:
                    formatted = f"MWK {float(total_book_balance):,.2f}"
                    summary_data.append(["Total Book Balance:", formatted])
                except (ValueError, TypeError):
                    summary_data.append(["Total Book Balance:", str(total_book_balance)])
            
            # Create summary table
            summary_table = ax_summary.table(
                cellText=summary_data,
                colWidths=[0.4, 0.6],
                cellLoc='left',
                loc='center',
                edges='open'
            )
            
            # Style summary table
            summary_table.auto_set_font_size(False)
            summary_table.set_fontsize(11)
            
            # Style header cells
            for i in range(len(summary_data)):
                # First column styling
                summary_table._cells[(i, 0)].set_facecolor('#f1f5f9')
                summary_table._cells[(i, 0)].set_text_props(fontweight='bold', color='#334155')
                
                # Second column styling
                cell = summary_table._cells[(i, 1)]
                cell.set_facecolor('#ffffff')
                
                # Highlight financial values
                cell_text = summary_data[i][1]
                if "MWK" in cell_text:
                    cell.set_text_props(fontweight='bold', color='#2563eb')
                elif cell_text.replace(',', '').isdigit():
                    cell.set_text_props(fontweight='bold', color='#059669')
            
            summary_table.scale(1, 1.8)
            
            # Paid Members Section
            ax_members = fig.add_subplot(gs[1])
            ax_members.axis('off')
            
            # Prepare members data
            member_data = []
            for _, row in paid_df.iterrows():
                name = str(row[name_col])
                amount = row[month_col]
                try:
                    formatted_amount = f"MWK {float(amount):,.2f}"
                except (ValueError, TypeError):
                    formatted_amount = str(amount)
                member_data.append([name, formatted_amount])
            
            if not member_data:
                logger.warning("No paid members data to display")
                plt.close(fig)
                return None
            
            # Add headers
            table_data = [["Member Name", "Amount"]] + member_data
            
            # Create members table
            members_table = ax_members.table(
                cellText=table_data,
                loc='center',
                cellLoc='left',
                colWidths=[0.6, 0.4]
            )
            
            # Style members table
            members_table.auto_set_font_size(False)
            members_table.set_fontsize(11)
            
            # Style header row
            for col in range(2):
                header_cell = members_table._cells[(0, col)]
                header_cell.set_facecolor('#2563eb')
                header_cell.set_text_props(color='white', fontweight='bold', fontsize=12)
            
            # Style data rows with alternating colors
            for i in range(1, len(table_data)):
                for col in range(2):
                    data_cell = members_table._cells[(i, col)]
                    if i % 2 == 0:
                        data_cell.set_facecolor('#f8fafc')
                    else:
                        data_cell.set_facecolor('#ffffff')
                    
                    # Right align amount column
                    if col == 1:
                        data_cell.set_text_props(ha='right')
            
            members_table.scale(1, 1.5)
            
            # Set figure title
            fig.suptitle(
                f"Paid Members Report - {data.get('month', '')} {data.get('year', '')}",
                fontsize=14,
                fontweight='bold',
                color='#1e293b',
                y=0.98
            )
            
            plt.tight_layout(rect=[0, 0, 1, 0.96])
            
            # Save to bytes buffer
            buf = BytesIO()
            plt.savefig(
                buf,
                format='png',
                bbox_inches='tight',
                dpi=150,
                facecolor=fig.get_facecolor(),
                edgecolor='none'
            )
            plt.close(fig)
            buf.seek(0)
            
            logger.info(f"Successfully generated image with {len(member_data)} paid members")
            return buf
            
        except Exception as e:
            logger.error(f"Error generating image: {str(e)}", exc_info=True)
            if 'fig' in locals():
                plt.close(fig)
            return None
    
    @staticmethod
    def generate_contribution_chart(data):
        """Generate a bar chart of contributions"""
        try:
            if not isinstance(data.get('data'), pd.DataFrame):
                data['data'] = pd.DataFrame(data['data'])
            
            month_col = data.get('month_col')
            name_col = data.get('name_col')
            
            if not month_col or not name_col:
                return None
            
            df = data['data']
            paid_df = df[~df[month_col].isna()]
            
            if paid_df.empty:
                return None
            
            # Sort by contribution amount
            paid_df = paid_df.sort_values(by=month_col, ascending=False)
            
            # Create figure
            fig, ax = plt.subplots(figsize=(12, 6), dpi=150)
            
            # Get top contributors (limit to 15 for readability)
            top_n = min(15, len(paid_df))
            top_df = paid_df.head(top_n)
            
            # Create bar chart
            bars = ax.barh(
                range(top_n),
                top_df[month_col].values,
                color='#3b82f6',
                edgecolor='#1d4ed8',
                linewidth=0.5
            )
            
            # Customize chart
            ax.set_yticks(range(top_n))
            ax.set_yticklabels(top_df[name_col].values, fontsize=9)
            ax.invert_yaxis()  # Highest on top
            
            # Add value labels on bars
            for i, (bar, value) in enumerate(zip(bars, top_df[month_col].values)):
                width = bar.get_width()
                ax.text(
                    width + (width * 0.01),
                    bar.get_y() + bar.get_height() / 2,
                    f'MWK {value:,.0f}',
                    va='center',
                    fontsize=8,
                    fontweight='bold'
                )
            
            # Add grid
            ax.xaxis.grid(True, linestyle='--', alpha=0.7)
            ax.set_axisbelow(True)
            
            # Set labels and title
            ax.set_xlabel('Contribution Amount (MWK)', fontweight='bold')
            ax.set_title(
                f'Top {top_n} Contributors - {data.get("month", "")} {data.get("year", "")}',
                fontsize=12,
                fontweight='bold',
                pad=20
            )
            
            plt.tight_layout()
            
            # Save to bytes buffer
            buf = BytesIO()
            plt.savefig(buf, format='png', bbox_inches='tight', dpi=150)
            plt.close(fig)
            buf.seek(0)
            
            return buf
            
        except Exception as e:
            logger.error(f"Error generating chart: {str(e)}")
            return None