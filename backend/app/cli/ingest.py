import argparse
import mimetypes
from pathlib import Path

from app.config import settings
from app.database import SessionLocal
from app.services.ingest import ingest_path, iter_inbox
from app.services.text import CATEGORIES


def main() -> None:
    parser = argparse.ArgumentParser(description="读取收件目录里的文件，拆成片段并写入知识库")
    parser.add_argument("--inbox", type=Path, default=None, help="收件目录，默认是项目里的 data/inbox")
    args = parser.parse_args()
    inbox = args.inbox or settings.inbox_path
    print(f"收件目录 {inbox}")
    print("把文件放进 design、regulation 或 other 子目录后再执行。")

    imported = skipped = rejected = failed = 0
    db = SessionLocal()
    try:
        found = False
        for category, path in iter_inbox(inbox):
            found = True
            label = f"{category}/{path.name}"
            try:
                content_type = mimetypes.guess_type(path.name)[0]
                result = ingest_path(
                    db,
                    path,
                    category=category,
                    content_type=content_type,
                )
            except ValueError as exc:
                failed += 1
                print(f"失败  {label}  {exc}")
                continue
            if result.action == "imported":
                imported += 1
                label_action = "入库"
            elif result.action == "skipped":
                skipped += 1
                label_action = "跳过"
            else:
                rejected += 1
                label_action = "无文字"
            print(f"{label_action}  {label}  {result.message}")
        if not found:
            names = "、".join(sorted(CATEGORIES))
            print(f"没有读到文件。请把 txt、md、pdf、docx 放进 {names}。")
    finally:
        db.close()
    print(f"完成：新入库 {imported}，已存在 {skipped}，无文字 {rejected}，失败 {failed}")


if __name__ == "__main__":
    main()
