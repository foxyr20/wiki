from pathlib import Path

INPUT_DIR = Path("./wiki")
OUTPUT_DIR = Path("./dump")
OUTPUT_FILE = "wiki_dump.txt"


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)
    output_path = OUTPUT_DIR / OUTPUT_FILE

    all_md = sorted(INPUT_DIR.rglob("*.md"))
    if not all_md:
        print(f"Нет .md файлов в папке: {INPUT_DIR}")
        return

    with open(output_path, "w", encoding="utf-8") as out:
        for md_path in all_md:
            out.write(f"\n\n<!-- Файл: {md_path.name} -->\n\n")
            out.write(md_path.read_text(encoding="utf-8"))
            out.write(f"\n\n<!-- Конец файла {md_path.name} -->\n")

    size = output_path.stat().st_size
    print(f"Готово: {output_path} ({size} символов)")


if __name__ == "__main__":
    main()
