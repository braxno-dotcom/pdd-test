# -*- coding: utf-8 -*-
"""Публикация страницы obmen-prav.html.

Запускать ТОЛЬКО когда заглушки в тексте заменены своими словами.
Делает три вещи и ни одной больше:
  1. снимает <meta name="robots" content="noindex, nofollow"> и убирает жёлтую плашку;
  2. вписывает страницу в sitemap.xml;
  3. проставляет ссылку на неё в блок «Тесты по темам» на всех страницах сайта.

Запуск:  python publier-obmen.py
Проверка без изменений:  python publier-obmen.py --posmotret
"""
import io, os, re, sys, glob

ZDES = os.path.dirname(os.path.abspath(__file__))
STRANICA = "obmen-prav.html"
SSYLKA = ' ·\n    <a href="obmen-prav.html">Обмен украинских прав</a>'
SAIT = "https://braxno-dotcom.github.io/pdd-test/"
SMOTRET = "--posmotret" in sys.argv


def chitat(f):
    return io.open(os.path.join(ZDES, f), encoding="utf-8").read()


def pisat(f, t):
    if SMOTRET:
        print("   (только смотрим, не пишу)")
        return
    io.open(os.path.join(ZDES, f), "w", encoding="utf-8", newline="\n").write(t)


def main():
    t = chitat(STRANICA)

    # --- 0. не публиковать с заглушками ---
    zaglushki = t.count('class="todo"')
    if zaglushki:
        print(f"⚠️  В {STRANICA} осталось заглушек: {zaglushki}.")
        print("   Заменить их своим текстом, иначе в поиск уйдёт пустая страница.")
        if not SMOTRET:
            return 1

    # --- 1. открыть для поиска ---
    if "noindex" in t:
        t = re.sub(r'\s*<!-- ⚠️ ЧЕРНОВИК.*?-->\s*', "\n  ", t, flags=re.S)
        t = re.sub(r'\s*<meta name="robots" content="noindex, nofollow">', "", t)
        t = re.sub(r'\s*<div class="draft">.*?</div>\s*', "\n\n  ", t, flags=re.S)
        pisat(STRANICA, t)
        print(f"1. {STRANICA}: запрет индексации снят, плашка черновика убрана")
    else:
        print(f"1. {STRANICA}: уже открыта для поиска")

    # --- 2. sitemap ---
    s = chitat("sitemap.xml")
    if STRANICA not in s:
        zapis = (f"  <url>\n    <loc>{SAIT}{STRANICA}</loc>\n"
                 f"    <changefreq>monthly</changefreq>\n    <priority>0.9</priority>\n  </url>\n")
        s = s.replace("</urlset>", zapis + "</urlset>")
        pisat("sitemap.xml", s)
        print("2. sitemap.xml: страница добавлена")
    else:
        print("2. sitemap.xml: уже там")

    # --- 3. перелинковка ---
    yakor = '<a href="alcool.html"'
    n = 0
    for f in sorted(glob.glob(os.path.join(ZDES, "*.html"))):
        imya = os.path.basename(f)
        if imya == STRANICA:
            continue
        d = chitat(imya)
        if yakor not in d or STRANICA in d:
            continue
        # ссылка ставится в конец блока «Тесты по темам», после «Алкоголь…»
        d = re.sub(r'(<a href="alcool\.html"[^>]*>[^<]*</a>)', r"\1" + SSYLKA, d, count=1)
        pisat(imya, d)
        n += 1
        print(f"3. {imya}: ссылка проставлена")
    if not n:
        print("3. перелинковка: добавлять некуда (уже стоит везде)")

    print("\nГотово. Осталось: git add -A && git commit && git push")
    return 0


if __name__ == "__main__":
    sys.exit(main())
