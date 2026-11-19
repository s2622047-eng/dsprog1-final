import sqlite3
import time
import re
import requests
from bs4 import BeautifulSoup


def setup_database():
    conn = sqlite3.connect("google_repos.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS repositories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            language TEXT,
            stars INTEGER
        )
    """)
    conn.commit()
    conn.close()


def parse_stars(star_str):
    if not star_str:
        return 0
    star_str = star_str.strip().replace(",", "")
    if "k" in star_str.lower():
        try:
            return int(float(star_str.lower().replace("k", "")) * 1000)
        except ValueError:
            return 0
    try:
        return int(star_str)
    except ValueError:
        return 0


def scrape_and_save():
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    extracted_data = []
    seen_repos = set()
    page = 1

    while True:
        url = f"https://github.com/orgs/google/repositories?page={page}"
        print(f"{page}ページ目を取得中: {url}")

        try:
            response = requests.get(url, headers=headers, timeout=15)
            print(f"  -> HTTPステータス: {response.status_code} (文字数: {len(response.text)})")
            if response.status_code != 200:
                break
        except Exception as e:
            print(f"  -> 通信エラー: {e}")
            break

        soup = BeautifulSoup(response.text, "html.parser")

        # リポジトリリンク (/google/リポジトリ名) を直接探す汎用ロジック
        repo_links = soup.select('a[itemprop="name codeRepository"], h3 a[href^="/google/"], h4 a[href^="/google/"]')
        
        # 上記で取れない場合、全aタグから /google/xxx 形式を抽出
        if not repo_links:
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if re.match(r"^/google/[^/]+$", href) and not href.startswith("/google/."):
                    repo_links.append(a)

        added_in_page = 0
        for a in repo_links:
            href = a.get("href", "")
            parts = [p for p in href.split("/") if p]
            if len(parts) != 2 or parts[0] != "google":
                continue
            repo_name = parts[1]
            if repo_name in seen_repos or repo_name in ["repositories", "people", "packages", "sponsors", "teams"]:
                continue
            seen_repos.add(repo_name)

            # 親要素(li または div)を遡って言語とスター数を取得
            container = a.find_parent("li") or a.find_parent("div", class_=re.compile("Box-row|ListItem|col"))
            language = "N/A"
            stars = 0

            if container:
                lang_tag = container.select_one('span[itemprop="programmingLanguage"]')
                if not lang_tag:
                    lang_tag = container.select_one('span[class*="repo-language-color"] + span')
                if lang_tag:
                    language = lang_tag.text.strip()

                star_tag = container.select_one("a[href$='/stargazers']")
                if star_tag:
                    stars = parse_stars(star_tag.text)

            extracted_data.append((repo_name, language, stars))
            added_in_page += 1

        print(f"  -> このページで {added_in_page} 件取得 (累計: {len(extracted_data)} 件)")

        if added_in_page == 0:
            break

        page += 1
        time.sleep(1)  # 課題要件：time.sleep(1)

    conn = sqlite3.connect("google_repos.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM repositories")

    for name, language, stars in extracted_data:
        cursor.execute(
            "INSERT INTO repositories (name, language, stars) VALUES (?, ?, ?)",
            (name, language, stars),
        )

    conn.commit()
    conn.close()
    print(f"\n合計 {len(extracted_data)} 件のデータを正常に保存しました。")


def display_saved_data():
    conn = sqlite3.connect("google_repos.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, language, stars FROM repositories")
    rows = cursor.fetchall()

    print("\n--- 保存されたデータ一覧 (SELECT結果) ---")
    print(f"{'ID':<5} | {'Repository Name':<35} | {'Language':<15} | {'Stars':<10}")
    print("-" * 73)
    for row in rows[:30]:  # 画面が埋まらないよう先頭30件を表示
        print(f"{row[0]:<5} | {row[1]:<35} | {row[2]:<15} | {row[3]:<10}")
    if len(rows) > 30:
        print(f"... 他 {len(rows) - 30} 件 (DBには全 {len(rows)} 件保存済み)")

    conn.close()


if __name__ == "__main__":
    setup_database()
    scrape_and_save()
    display_saved_data()
