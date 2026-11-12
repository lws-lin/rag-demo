from enum import Enum


class DocumentStatus(str, Enum):
    pending = "pending"
    parsing = "parsing"
    review = "review"
    published = "published"
    rejected = "rejected"
    offline = "offline"


REVIEW_DECISIONS = {DocumentStatus.published, DocumentStatus.rejected, DocumentStatus.offline}


def status_in_sql() -> str:
    quoted = ", ".join(f"'{item.value}'" for item in DocumentStatus)
    return f"status in ({quoted})"
