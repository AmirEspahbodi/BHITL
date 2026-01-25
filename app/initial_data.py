import json
import logging
from pathlib import Path

from sqlmodel import Session

from app.core.db import engine

# Assuming init_db is used elsewhere or imported for side effects
from app.models import Comment as Samples
from app.models import Principle

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init_principles() -> None:
    with Session(engine) as session:
        json_file_path = Path(__file__).resolve().parent.parent / "principles.json"

        if not json_file_path.exists():
            logger.error(f"Principles file not found at: {json_file_path}")
            return

        logger.info(f"Loading principles from {json_file_path}")

        try:
            with open(json_file_path, "r", encoding="utf-8") as f:
                principles_data = json.load(f)

            count = 0
            for item in principles_data:
                principle = Principle.model_validate(item)
                session.merge(principle)
                count += 1

            session.commit()
            logger.info(f"Successfully loaded/updated {count} principles.")

            # Cleanup: Remove the file after successful commit
            json_file_path.unlink()
            logger.info(f"Deleted source file: {json_file_path}")

        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON: {e}")
        except Exception as e:
            logger.error(f"An error occurred while loading principles: {e}")
            session.rollback()


def init_samples() -> None:
    with Session(engine) as session:
        json_file_path = Path(__file__).resolve().parent.parent / "samples.json"

        if not json_file_path.exists():
            logger.error(f"Samples file not found at: {json_file_path}")
            return

        logger.info(f"Loading samples from {json_file_path}")

        try:
            with open(json_file_path, "r", encoding="utf-8") as f:
                samples_data = json.load(f)

            count = 0
            for item in samples_data:
                # Explicit mapping retained as per original code
                samples = Samples.model_validate(
                    {
                        "id": item["id"],
                        "preceding": item["preceding"],
                        "target": item["target"],
                        "following": item["following"],
                        "A1_Score": item["A1_Score"],
                        "A2_Score": item["A2_Score"],
                        "A3_Score": item["A3_Score"],
                        "principle_id": item["principle_id"],
                        "llm_justification": item["llm_justification"],
                        "llm_evidence_quote": item["llm_evidence_quote"],
                    }
                )
                session.merge(samples)
                count += 1

            session.commit()
            logger.info(f"Successfully loaded/updated {count} samples.")

            # Cleanup: Remove the file after successful commit
            json_file_path.unlink()
            logger.info(f"Deleted source file: {json_file_path}")

        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON: {e}")
        except Exception as e:
            logger.error(f"An error occurred while loading samples: {e}")
            session.rollback()


def main() -> None:
    logger.info("Creating initial data")
    init_principles()
    init_samples()
    logger.info("Initial data created")


if __name__ == "__main__":
    main()
