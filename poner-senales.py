# -*- coding: utf-8 -*-
"""Вставляет дорожные знаки в страницы французского ПДД.

    python poner-senales.py --prueba    показать, к чему прицепятся знаки, ничего не меняя
    python poner-senales.py             вставить

⚠️ Знаки взяты из испанского тренажёра и это НЕ халтура: по Венской конвенции формы
и цвета общие для Франции, Испании, Швеции, Румынии. STOP, «уступи дорогу», круг
с красной каймой, синий круг предписания — одни и те же. Файлы официальные,
из каталога (см. pdd-es/ИСТОЧНИКИ-ЗНАКОВ.md).

⚠️ Банк вопросов у французского сайта ВШИТ В КАЖДУЮ из семи страниц, поэтому правка
идёт по всем семи одинаково. Это же причина, по которой знаки кладутся прямо в файл,
а не отдельным скриптом: второй запрос может не прийти, и знак молча исчезнет —
на испанском сайте так и вышло.

Привязка знака к вопросу — по ключевым словам, и только там, где вопрос ПРО САМ ЗНАК
или разметку. Вопрос, где знак просто упомянут, картинки не получает: показать знак
рядом с вопросом о другом — значит сбить человека.
"""
import io
import os
import re
import sys

PAGINAS = ["pdd-test.html", "vitesse.html", "panneaux.html", "priorite.html",
           "alcool.html", "amendes.html", "securite.html"]

FUENTE_SENALES = r"..\pdd-es\senales.js"
FUENTE_MARCAS = r"..\pdd-es\marcas.js"

# Ключевое слово во французском вопросе → какой знак показать.
# Порядок важен: первое совпадение и берётся, поэтому точные фразы идут раньше общих.
REGLAS = [
    # ⚠️ «Уступи дорогу» проверяется РАНЬШЕ STOP: в вопросах их сравнивают в одной
    # фразе («impose un arrêt complet comme le Stop»), и по порядку выигрывал STOP —
    # человеку показывался не тот знак. Поймано сухим прогоном.
    (r"c[ée]dez le passage", "ceda_el_paso"),
    (r"\bSTOP\b", "stop"),
    (r"sens interdit", "entrada_prohibida"),
    (r"interdiction de d[ée]passer|d[ée]passement est interdit|interdit de d[ée]passer",
     "prohibido_adelantar"),
    (r"ligne continue", "marca_continua"),
    (r"ligne discontinue", "marca_discontinua"),
    (r"feu (orange|jaune) clignotant", "semaforo_ambar_intermitente"),
    (r"feu (orange|jaune) fixe|feu orange\b", "semaforo_ambar"),
    (r"stationnement et l.arr[êe]t sont interdits|arr[êe]t et stationnement interdits",
     "prohibido_parar"),
    (r"stationnement interdit", "prohibido_estacionar"),
    (r"passage [àa] niveau", "paso_nivel_barreras"),
    (r"rond-point|carrefour giratoire|giratoire", "rotonda_obligatoria"),
    (r"passage pi[ée]ton", "paso_peatones"),
    (r"chauss[ée]e glissante", "pavimento_deslizante"),
    (r"travaux", "obras"),
    (r"animaux", "animales_sueltos"),
    (r"pr[ée]sence d.enfants|sortie d.[ée]cole", "ninos"),
    (r"cyclistes?\b", "ciclistas_peligro"),
    (r"virage dangereux|virage [àa] droite", "curva_derecha"),
    (r"r[ée]tr[ée]cissement", "estrechamiento"),
    (r"vitesse limit[ée]e [àa] 50|panneau de limitation", "velocidad_maxima"),
    (r"fin de toutes les interdictions|fin d.interdiction", "fin_prohibiciones"),
    (r"zone r[ée]sidentielle|zone de rencontre", "calle_residencial"),
]

# ⚠️ Вопросы-исключения: слово есть, а знака показывать нельзя — речь не о знаке.
# Например «сколько баллов снимут за проезд на красный»: там знак ни при чём.
VETO = re.compile(
    # вопрос про деньги и баллы — знак там ни при чём
    r"points?|amende|euros?|retrait|retire|permis probatoire|alcool"
    # ⚠️ «Stop & Start» — система двигателя, а не знак. Поймано сухим прогоном:
    # ей доставался восьмиугольник, и вопрос про расход топлива выглядел дурдомом.
    r"|stop *& *start|batterie|carburant"
    # ⚠️ И вопросы О ВНЕШНЕМ ВИДЕ знака: «какого он цвета», «что нарисовано внутри»,
    # «перечёркнут ли одной полосой». Показать такой знак — значит дать ответ даром.
    # Поймано сухим прогоном: три вопроса из двадцати одного были именно такие.
    r"|de couleur|barr[ée]|triangulaire avec|repr[ée]sente|dessin", re.I)

# ⚠️ Знак показываем, только если вопрос ПРО ЗНАК ИЛИ РАЗМЕТКУ, а не про правило,
# где слово случайно встретилось. Без этого «велосипедист имеет право ехать
# посередине» получал треугольник с велосипедом и сбивал с толку.
HABLA_DE_SENAL = re.compile(r"panneau|ligne|marquage|feu|signal|balise|zone de rencontre", re.I)


# ⚠️ Своих вопросов про знаки во французском банке почти нет: из 477 к знакам
# цепляются восемнадцать, и то косвенно. Поэтому добавляем прямые — «что
# означает этот знак», по одному на каждый знак набора. Формат банка
# французского сайта: {s, q, q_ru, o, a}, варианты по-французски.
NUEVAS_JS = '\n        // --- ВОПРОСЫ ПРО ЗНАКИ (добавлены 17 сен 2026) ---\n        {s: "stop", q: "Que signifie ce panneau ?", q_ru: "Что означает этот знак?", o: ["Marquer l\'arrêt complet avant la ligne", "Ralentir et passer avec prudence", "Céder le passage sans s\'arrêter"], a: 0},\n        {s: "ceda_el_paso", q: "Que signifie ce panneau ?", q_ru: "Что означает этот знак?", o: ["Céder le passage sans obligation de s\'arrêter", "Marquer l\'arrêt complet obligatoire", "Avoir la priorité sur l\'autre voie"], a: 0},\n        {s: "calzada_prioridad", q: "Que signifie ce panneau ?", q_ru: "Что означает этот знак?", o: ["Route à caractère prioritaire", "Céder le passage au prochain carrefour", "Fin de la route prioritaire"], a: 0},\n        {s: "fin_prioridad", q: "Que signifie ce panneau ?", q_ru: "Что означает этот знак?", o: ["Fin de la route prioritaire", "Début de la route prioritaire", "Priorité réservée aux poids lourds"], a: 0},\n        {s: "circulacion_prohibida", q: "Que signifie ce panneau ?", q_ru: "Что означает этот знак?", o: ["Circulation interdite dans les deux sens", "Fin de toutes les interdictions", "Voie réservée aux véhicules lents"], a: 0},\n        {s: "entrada_prohibida", q: "Que signifie ce panneau ?", q_ru: "Что означает этот знак?", o: ["Sens interdit à tout véhicule", "Stationnement interdit de ce côté", "Route barrée pour travaux"], a: 0},\n        {s: "prohibido_camiones", q: "Que signifie ce panneau ?", q_ru: "Что означает этот знак?", o: ["Accès interdit aux camions de marchandises", "Accès interdit aux autocars de ligne", "Accès interdit avec une remorque"], a: 0},\n        {s: "prohibido_bicicletas", q: "Que signifie ce panneau ?", q_ru: "Что означает этот знак?", o: ["Accès interdit aux cycles", "Piste obligatoire pour les cycles", "Stationnement réservé aux vélos"], a: 0},\n        {s: "velocidad_maxima", q: "Que signifie ce panneau ?", q_ru: "Что означает этот знак?", o: ["Vitesse maximale autorisée", "Vitesse minimale obligatoire", "Vitesse conseillée sur la section"], a: 0},\n        {s: "velocidad_minima", q: "Que signifie ce panneau ?", q_ru: "Что означает этот знак?", o: ["Vitesse minimale obligatoire", "Vitesse maximale autorisée", "Distance minimale entre véhicules"], a: 0},\n        {s: "prohibido_adelantar", q: "Que signifie ce panneau ?", q_ru: "Что означает этот знак?", o: ["Interdiction de dépasser les véhicules", "Interdiction de rouler en parallèle", "Interdiction de remorquer un véhicule"], a: 0},\n        {s: "prohibido_parar", q: "Que signifie ce panneau ?", q_ru: "Что означает этот знак?", o: ["Arrêt et stationnement interdits", "Stationnement interdit plus d\'une heure", "Zone de livraison réservée"], a: 0},\n        {s: "prohibido_estacionar", q: "Que signifie ce panneau ?", q_ru: "Что означает этот знак?", o: ["Stationnement interdit de ce côté", "Arrêt interdit même une minute", "Stationnement payant avec ticket"], a: 0},\n        {s: "sentido_obligatorio", q: "Que signifie ce panneau ?", q_ru: "Что означает этот знак?", o: ["Direction obligatoire à suivre", "Direction interdite à ce carrefour", "Voie de service pour riverains"], a: 0},\n        {s: "paso_obligatorio", q: "Que signifie ce panneau ?", q_ru: "Что означает этот знак?", o: ["Contournement obligatoire par ce côté", "Passage interdit par ce côté", "Voie réservée aux autobus"], a: 0},\n        {s: "rotonda_obligatoria", q: "Que signifie ce panneau ?", q_ru: "Что означает этот знак?", o: ["Carrefour à sens giratoire obligatoire", "Carrefour où tourner est interdit", "Zone de manoeuvre pour camions"], a: 0},\n        {s: "via_ciclistas", q: "Que signifie ce panneau ?", q_ru: "Что означает этот знак?", o: ["Piste obligatoire pour les cycles", "Accès interdit aux bicyclettes", "Stationnement réservé aux vélos"], a: 0},\n        {s: "fin_prohibiciones", q: "Que signifie ce panneau ?", q_ru: "Что означает этот знак?", o: ["Fin de toutes les interdictions précédentes", "Début d\'une zone sans limitation", "Fin de la chaussée revêtue"], a: 0},\n        {s: "fin_velocidad_maxima", q: "Que signifie ce panneau ?", q_ru: "Что означает этот знак?", o: ["Fin de cette limitation de vitesse", "Début de cette limitation de vitesse", "Vitesse conseillée sur la section"], a: 0},\n        {s: "semaforo", q: "Que signifie ce panneau ?", q_ru: "Что означает этот знак?", o: ["Feux tricolores plus loin", "Zone surveillée par des caméras", "Carrefour réglé par un agent"], a: 0},\n        {s: "paso_nivel_barreras", q: "Que signifie ce panneau ?", q_ru: "Что означает этот знак?", o: ["Passage à niveau avec barrières", "Chantier protégé par des barrières", "Pont mobile au-dessus du fleuve"], a: 0},\n        {s: "paso_nivel_sin_barreras", q: "Que signifie ce panneau ?", q_ru: "Что означает этот знак?", o: ["Passage à niveau sans barrières", "Gare ferroviaire à proximité", "Passage souterrain pour les trains"], a: 0},\n        {s: "curva_derecha", q: "Que signifie ce panneau ?", q_ru: "Что означает этот знак?", o: ["Virage dangereux vers la droite", "Déviation obligatoire vers la droite", "Sortie de véhicules sur la droite"], a: 0},\n        {s: "curva_izquierda", q: "Que signifie ce panneau ?", q_ru: "Что означает этот знак?", o: ["Virage dangereux vers la gauche", "Déviation obligatoire vers la gauche", "Sortie de véhicules sur la gauche"], a: 0},\n        {s: "baden", q: "Que signifie ce panneau ?", q_ru: "Что означает этот знак?", o: ["Ralentisseur sur la chaussée", "Cassis ou dos d\'âne sans visibilité", "Passage supérieur pour piétons"], a: 0},\n        {s: "estrechamiento", q: "Que signifie ce panneau ?", q_ru: "Что означает этот знак?", o: ["Chaussée rétrécie plus loin", "Tunnel étroit sans éclairage", "Pont à charge limitée"], a: 0},\n        {s: "obras", q: "Que signifie ce panneau ?", q_ru: "Что означает этот знак?", o: ["Travaux sur la chaussée", "Usine en bordure de route", "Zone de chargement de matériaux"], a: 0},\n        {s: "obras_temporal", q: "Que signifie ce panneau ?", q_ru: "Что означает этот знак?", o: ["Signalisation temporaire de chantier", "Panneau d\'information sans obligation", "Panneau que l\'on peut ignorer"], a: 0},\n        {s: "pavimento_deslizante", q: "Que signifie ce panneau ?", q_ru: "Что означает этот знак?", o: ["Chaussée glissante, adhérence réduite", "Section avec ralentisseurs successifs", "Virage couvert de gravillons"], a: 0},\n        {s: "peatones_peligro", q: "Que signifie ce panneau ?", q_ru: "Что означает этот знак?", o: ["Passage de piétons dangereux", "Zone piétonne fermée aux voitures", "Arrêt de bus scolaire"], a: 0},\n        {s: "ninos", q: "Que signifie ce panneau ?", q_ru: "Что означает этот знак?", o: ["Présence habituelle d\'enfants", "Aire de jeux fermée à la circulation", "Arrêt de ramassage scolaire"], a: 0},\n        {s: "ciclistas_peligro", q: "Que signifie ce panneau ?", q_ru: "Что означает этот знак?", o: ["Débouché fréquent de cyclistes", "Piste réservée aux bicyclettes", "Interdiction de circuler à vélo"], a: 0},\n        {s: "animales_sueltos", q: "Que signifie ce panneau ?", q_ru: "Что означает этот знак?", o: ["Passage possible d\'animaux sauvages", "Ferme avec bétail à proximité", "Réserve naturelle protégée"], a: 0},\n        {s: "otros_peligros", q: "Que signifie ce panneau ?", q_ru: "Что означает этот знак?", o: ["Danger sans panneau spécifique", "Panne fréquente des feux tricolores", "Section contrôlée par radar"], a: 0},\n        {s: "paso_peatones", q: "Que signifie ce panneau ?", q_ru: "Что означает этот знак?", o: ["Passage pour piétons, ils ont priorité", "Trottoir surélevé le long de la voie", "Chemin réservé aux piétons"], a: 0},\n        {s: "estacionamiento", q: "Que signifie ce panneau ?", q_ru: "Что означает этот знак?", o: ["Emplacement où le stationnement est permis", "Zone d\'arrêt rapide pour les taxis", "Parking réservé à la police"], a: 0},\n        {s: "calle_residencial", q: "Que signifie ce panneau ?", q_ru: "Что означает этот знак?", o: ["Zone de rencontre : le piéton est prioritaire", "Quartier résidentiel sans issue", "Parking réservé aux riverains"], a: 0},\n        {s: "marca_continua", q: "Que signifie ce marquage ?", q_ru: "Что означает эта разметка?", o: ["Ligne continue : franchissement interdit", "Ligne franchissable pour dépasser", "Simple séparation des deux sens"], a: 0},\n        {s: "marca_discontinua", q: "Que signifie ce marquage ?", q_ru: "Что означает эта разметка?", o: ["Ligne discontinue : franchissement permis", "Ligne qu\'on ne peut jamais franchir", "Ligne réservée aux deux-roues"], a: 0},\n        {s: "semaforo_ambar", q: "Que faut-il faire à ce feu ?", q_ru: "Что делать на этом сигнале?", o: ["S\'arrêter, sauf si freiner est dangereux", "Accélérer pour passer avant le rouge", "Continuer sans aucune obligation"], a: 0},\n        {s: "semaforo_ambar_intermitente", q: "Que signifie ce feu ?", q_ru: "Что означает этот сигнал?", o: ["Passer avec prudence : la signalisation s\'applique", "S\'arrêter complètement et attendre le vert", "Que le feu est totalement en panne"], a: 0},\n'


def leer(nombre):
    return io.open(nombre, encoding="utf-8").read()


def bloque_senales():
    """Знаки и разметка одним куском кода, готовым к вставке в страницу."""
    s = leer(FUENTE_SENALES).replace(
        'if (typeof module !== "undefined") module.exports = SENALES;', "")
    m = leer(FUENTE_MARCAS).replace(
        'if (typeof module !== "undefined") module.exports = MARCAS;', "")
    return "<script>\n" + s + m + "\nObject.assign(SENALES, MARCAS);\n</script>\n"


def elegir_senal(pregunta):
    if VETO.search(pregunta):
        return None
    if not HABLA_DE_SENAL.search(pregunta):
        return None
    for patron, clave in REGLAS:
        if re.search(patron, pregunta, re.I):
            return clave
    return None


def preguntas_de(texto):
    """Вытаскиваем вопросы банка как есть, вместе с их точным написанием."""
    return re.findall(r'\{q: "((?:[^"\\]|\\.)*)"', texto)


def main():
    solo_mirar = "--prueba" in sys.argv
    base = leer(PAGINAS[0])
    preguntas = preguntas_de(base)
    print("вопросов в банке:", len(preguntas))

    parejas, conteo = [], {}
    for q in preguntas:
        clave = elegir_senal(q)
        if clave:
            parejas.append((q, clave))
            conteo[clave] = conteo.get(clave, 0) + 1

    print("получат знак:", len(parejas))
    for clave, n in sorted(conteo.items(), key=lambda kv: -kv[1]):
        print("   %-28s %d" % (clave, n))

    if solo_mirar:
        print("\nПримеры (проверить глазами, не сбивает ли знак):")
        for q, clave in parejas[:18]:
            print("  [%s] %s" % (clave, q[:96]))
        return

    disponibles = set(re.findall(r"^  (\w+):", leer(FUENTE_SENALES), re.M))
    disponibles |= set(re.findall(r"^  (\w+):", leer(FUENTE_MARCAS), re.M))
    faltan = {c for _, c in parejas} - disponibles
    if faltan:
        print("⚠️ таких знаков нет в наборе:", ", ".join(sorted(faltan)))
        return

    for nombre in PAGINAS:
        s = leer(nombre)
        if "SENALES_INSERTADAS" in s:
            print(nombre, "— уже с знаками, пропуск")
            continue

        # 1. место под знак над вопросом
        s = s.replace('<h2 id="question">',
                      '<div id="senal-zona"></div>\n        <h2 id="question">', 1)

        # 2. сами знаки + пометка, что страница уже обработана
        s = s.replace("<script>\n// SENALES", "<script>\n// SENALES")   # no-op, читаемость
        s = s.replace("const questions = [",
                      "/* SENALES_INSERTADAS */\nconst questions = [", 1)
        s = s.replace("</head>", bloque_senales() + "</head>", 1)

        # 3. отрисовка: знак появляется вместе с вопросом и исчезает, если его нет
        s = s.replace('document.getElementById("question").textContent = item.q;',
                      'document.getElementById("question").textContent = item.q;\n'
                      '    var zonaSenal = document.getElementById("senal-zona");\n'
                      '    if (zonaSenal) zonaSenal.innerHTML = (item.s && SENALES[item.s]) ? SENALES[item.s] : "";',
                      1)

        # 4. немного стиля
        s = s.replace("</style>",
                      "#senal-zona { text-align: center; margin: 0 0 12px; }\n"
                      "#senal-zona svg { width: 120px; height: 120px; }\n</style>", 1)

        # 5. новые вопросы про знаки — перед закрытием банка
        cierre = "];\n// КОНЕЦ ТВОИХ ВОПРОСОВ"
        if cierre in s:
            s = s.replace(cierre, NUEVAS_JS + cierre, 1)
        else:
            print("  ⚠️ конец банка не найден в", nombre)

        # 6. привязка знаков к существующим вопросам
        puestos = 0
        for q, clave in parejas:
            viejo = '{q: "%s"' % q
            nuevo = '{s: "%s", q: "%s"' % (clave, q)
            if viejo in s:
                s = s.replace(viejo, nuevo)
                puestos += 1
        io.open(nombre, "w", encoding="utf-8").write(s)
        print("%-16s знаков привязано: %d" % (nombre, puestos))


if __name__ == "__main__":
    main()
