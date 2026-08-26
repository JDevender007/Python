"""
Currency Converter API - Exporter Module
Handles exporting conversion data and rates to CSV and JSON.
"""

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any
from .config import EXPORTS_DIR
from .logger import logger


class CurrencyExporter:
    """Handles exporting currency data."""

    def __init__(self, export_dir: Path = EXPORTS_DIR):
        self.export_dir = export_dir
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def export_conversion(self, conversion, filename: str = None) -> Optional[Path]:
        """Export single conversion to CSV."""
        if not conversion:
            logger.warning("No conversion data to export")
            return None

        filename = filename or f"conversion_{conversion.from_currency}_{conversion.to_currency}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        filepath = self.export_dir / filename

        try:
            with open(filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Field", "Value"])
                writer.writerow(["From Currency", conversion.from_currency])
                writer.writerow(["To Currency", conversion.to_currency])
                writer.writerow(["Amount", conversion.amount])
                writer.writerow(["Result", conversion.result])
                writer.writerow(["Exchange Rate", conversion.rate])
                writer.writerow(["Timestamp", datetime.fromtimestamp(conversion.timestamp).strftime("%Y-%m-%d %H:%M:%S")])
                writer.writerow(["Source", conversion.source])
                writer.writerow(["Exported At", datetime.now().isoformat()])

            logger.info(f"Exported conversion to CSV: {filepath}")
            return filepath

        except Exception as e:
            logger.error(f"Error exporting conversion to CSV: {e}")
            return None

    def export_rates(self, rates_response, filename: str = None) -> Optional[Path]:
        """Export exchange rates to CSV."""
        if not rates_response or not rates_response.rates:
            logger.warning("No rates data to export")
            return None

        base = rates_response.base
        filename = filename or f"rates_{base}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        filepath = self.export_dir / filename

        try:
            with open(filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Base Currency", base])
                writer.writerow(["Date", rates_response.date or datetime.fromtimestamp(rates_response.timestamp).strftime("%Y-%m-%d")])
                writer.writerow(["Source", rates_response.source])
                writer.writerow([])
                writer.writerow(["Target Currency", "Rate (1 Base = X Target)"])

                for currency in sorted(rates_response.rates.keys()):
                    writer.writerow([currency, rates_response.rates[currency]])

                writer.writerow([])
                writer.writerow(["Exported At", datetime.now().isoformat()])

            logger.info(f"Exported {len(rates_response.rates)} rates to CSV: {filepath}")
            return filepath

        except Exception as e:
            logger.error(f"Error exporting rates to CSV: {e}")
            return None

    def export_history(self, history: List[Dict], filename: str = None) -> Optional[Path]:
        """Export conversion history to CSV."""
        if not history:
            logger.warning("No history to export")
            return None

        filename = filename or f"conversion_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        filepath = self.export_dir / filename

        try:
            with open(filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Timestamp", "From Currency", "To Currency", "Amount", "Result", "Rate"])

                for entry in history:
                    writer.writerow([
                        entry.get("timestamp", ""),
                        entry.get("from_currency", ""),
                        entry.get("to_currency", ""),
                        entry.get("amount", ""),
                        entry.get("result", ""),
                        entry.get("rate", "")
                    ])

            logger.info(f"Exported {len(history)} history entries to CSV: {filepath}")
            return filepath

        except Exception as e:
            logger.error(f"Error exporting history to CSV: {e}")
            return None

    def export_conversion_json(self, conversion, filename: str = None) -> Optional[Path]:
        """Export single conversion to JSON."""
        if not conversion:
            logger.warning("No conversion data to export")
            return None

        filename = filename or f"conversion_{conversion.from_currency}_{conversion.to_currency}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = self.export_dir / filename

        try:
            data = {
                "exported_at": datetime.now().isoformat(),
                "conversion": {
                    "from_currency": conversion.from_currency,
                    "to_currency": conversion.to_currency,
                    "amount": conversion.amount,
                    "result": conversion.result,
                    "rate": conversion.rate,
                    "timestamp": datetime.fromtimestamp(conversion.timestamp).isoformat(),
                    "source": conversion.source
                }
            }

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            logger.info(f"Exported conversion to JSON: {filepath}")
            return filepath

        except Exception as e:
            logger.error(f"Error exporting conversion to JSON: {e}")
            return None

    def export_rates_json(self, rates_response, filename: str = None) -> Optional[Path]:
        """Export exchange rates to JSON."""
        if not rates_response or not rates_response.rates:
            logger.warning("No rates data to export")
            return None

        base = rates_response.base
        filename = filename or f"rates_{base}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = self.export_dir / filename

        try:
            data = {
                "exported_at": datetime.now().isoformat(),
                "base_currency": base,
                "date": rates_response.date,
                "timestamp": datetime.fromtimestamp(rates_response.timestamp).isoformat() if rates_response.timestamp > 0 else None,
                "source": rates_response.source,
                "total_currencies": len(rates_response.rates),
                "rates": rates_response.rates
            }

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            logger.info(f"Exported rates to JSON: {filepath}")
            return filepath

        except Exception as e:
            logger.error(f"Error exporting rates to JSON: {e}")
            return None

    def export_history_json(self, history: List[Dict], filename: str = None) -> Optional[Path]:
        """Export conversion history to JSON."""
        if not history:
            logger.warning("No history to export")
            return None

        filename = filename or f"conversion_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = self.export_dir / filename

        try:
            data = {
                "exported_at": datetime.now().isoformat(),
                "total_entries": len(history),
                "history": history
            }

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            logger.info(f"Exported history to JSON: {filepath}")
            return filepath

        except Exception as e:
            logger.error(f"Error exporting history to JSON: {e}")
            return None


def create_exporter(export_dir: Path = None) -> CurrencyExporter:
    """Factory function to create exporter."""
    return CurrencyExporter(export_dir) if export_dir else CurrencyExporter()