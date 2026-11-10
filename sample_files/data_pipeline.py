"""
Hermes Data Pipeline Module
Provides stream processing, batch transformation, and schema validation.
"""

from typing import List, Dict, Any, Optional
import time
import json


class RecordValidator:
    """Validates records against defined schema rules and types."""

    def __init__(self, required_fields: Optional[List[str]] = None):
        """
        Initialize the validator with required field names.

        Args:
            required_fields: List of keys that must exist in valid records.
        """
        self.required_fields = required_fields or ["id", "timestamp", "payload"]

    def validate(self, record: Dict[str, Any]) -> bool:
        """
        Check if a single dictionary record satisfies the schema.

        Args:
            record: Data item to validate.

        Returns:
            True if all required fields are present and valid, False otherwise.
        """
        if not isinstance(record, dict):
            return False
        for field in self.required_fields:
            if field not in record or record[field] is None:
                return False
        return True


class StreamPipeline:
    """
    Core pipeline orchestrator for transforming and ingesting records.
    Maintains statistics and supports batch execution.
    """

    def __init__(self, name: str, batch_size: int = 100):
        """
        Initialize a new StreamPipeline instance.

        Args:
            name: Identifier for this processing pipeline.
            batch_size: Number of records to group per execution cycle.
        """
        self.name = name
        self.batch_size = max(1, batch_size)
        self.validator = RecordValidator()
        self.processed_count = 0
        self.error_count = 0

    def process_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize and enrich an incoming record.

        Args:
            record: Raw input dictionary.

        Returns:
            Enriched dictionary with status and processed_at timestamp.
        """
        if not self.validator.validate(record):
            self.error_count += 1
            raise ValueError(f"Invalid record structure: {record}")

        enriched = dict(record)
        enriched["processed_at"] = time.time()
        enriched["status"] = "VERIFIED"
        self.processed_count += 1
        return enriched

    def batch_process(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Process an iterable of records sequentially with error isolation.

        Args:
            records: Collection of record dictionaries.

        Returns:
            List of successfully transformed records.
        """
        output = []
        for item in records:
            try:
                processed = self.process_record(item)
                output.append(processed)
            except ValueError:
                continue
        return output

    def get_metrics(self) -> Dict[str, Any]:
        """
        Retrieve operational throughput and failure statistics.

        Returns:
            Dictionary containing processed_count, error_count, and pipeline name.
        """
        return {
            "pipeline": self.name,
            "processed": self.processed_count,
            "errors": self.error_count,
            "success_rate": (
                self.processed_count / (self.processed_count + self.error_count)
                if (self.processed_count + self.error_count) > 0
                else 1.0
            ),
        }
