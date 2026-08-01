"""Editorial 15-page natal PDF inspired by the approved Orbitia natal mockup."""

from __future__ import annotations

import math
import os
from xml.sax import saxutils


def _safe(value, fallback: str = "") -> str:
    return saxutils.escape(str(value if value not in (None, "") else fallback))


def _score(value, fallback: int = 5) -> int:
    try:
        return max(1, min(10, round(float(value))))
    except (TypeError, ValueError):
        return fallback


def _items(values, limit: int = 4) -> str:
    if not isinstance(values, list):
        return ""
    return "".join(f"<li>{_safe(value)}</li>" for value in values[:limit])


def _category(report: dict, key: str) -> dict:
    return next((item for item in report.get("categories", []) if item.get("key") == key), {})


def _bars(values, fallback_names: list[str]) -> str:
    source = values if isinstance(values, list) else []
    rows = []
    for index, name in enumerate(fallback_names):
        item = source[index] if index < len(source) and isinstance(source[index], dict) else {}
        value = _score(item.get("value"), 7 - index)
        rows.append(
            f'<div class="bar"><span>{_safe(item.get("name"), name)}</span>'
            f'<i><b style="width:{value * 10}%"></b></i><em>{value}/10</em></div>'
        )
    return "".join(rows)


def _radar(values: list[dict]) -> str:
    values = values or []
    labels = [str(item.get("name") or "Сфера") for item in values[:6]]
    scores = [_score(item.get("value"), 6) for item in values[:6]]
    while len(labels) < 6:
        labels.append(["Огонь", "Земля", "Воздух", "Вода", "Кардин.", "Фиксир."][len(labels)])
        scores.append(6)
    center, radius = 150, 92
    rings, axes, points, texts = [], [], [], []
    for ring in range(1, 5):
        ring_points = []
        for index in range(6):
            angle = 2 * math.pi * index / 6 - math.pi / 2
            r = radius * ring / 4
            ring_points.append(f"{center + math.cos(angle)*r:.1f},{center + math.sin(angle)*r:.1f}")
        rings.append(f'<polygon points="{" ".join(ring_points)}"/>')
    for index, (label, value) in enumerate(zip(labels, scores)):
        angle = 2 * math.pi * index / 6 - math.pi / 2
        ox, oy = center + math.cos(angle)*radius, center + math.sin(angle)*radius
        px, py = center + math.cos(angle)*radius*value/10, center + math.sin(angle)*radius*value/10
        lx, ly = center + math.cos(angle)*(radius+28), center + math.sin(angle)*(radius+28)
        axes.append(f'<line x1="{center}" y1="{center}" x2="{ox:.1f}" y2="{oy:.1f}"/>')
        points.append(f"{px:.1f},{py:.1f}")
        texts.append(f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle">{_safe(label)}</text>')
    return f'<svg class="radar" viewBox="0 0 300 300"><g class="grid">{"".join(rings+axes)}</g><polygon class="area" points="{" ".join(points)}"/><polygon class="line" points="{" ".join(points)}"/><g>{"".join(texts)}</g></svg>'


def _section_page(number: int, key: str, report: dict, subtitle: str, visual: str = "orbit") -> str:
    data = _category(report, key)
    score = _score(data.get("score"), 7)
    keywords = list(data.get("keywords") or ["смысл", "опора", "вектор"])
    keywords = (keywords + ["опора", "вектор", "ресурс"])[:3]
    if visual == "bars":
        visual_html = _bars(
            [{"name": name, "value": max(1, score-index)} for index, name in enumerate(keywords)],
            keywords,
        )
    elif visual == "battery":
        visual_html = f'<div class="battery"><div style="width:{score*10}%"><span>{score}/10</span></div></div><div class="battery-labels"><span>ресурс</span><span>нагрузка</span></div>'
    else:
        visual_html = f'<div class="orbit"><i></i><b>{_safe(data.get("title"), key)}</b><span>{_safe(keywords[0])}</span><span>{_safe(keywords[1])}</span><span>{_safe(keywords[2])}</span></div>'
    return f"""
    <section class="page section-page">
      <header class="section-head"><span>— — {number:02d} · {_safe(data.get('title'), key)}</span><small>{_safe(subtitle)}</small></header>
      <article class="lead-card"><h2>{_safe(data.get('main_takeaway'), data.get('title'))}</h2><p>{_safe(data.get('summary'))}</p></article>
      <div class="section-grid">
        <div class="copy-cards">
          <article><h3>Как проявляется</h3><ul>{_items(data.get('manifestations'))}</ul></article>
          <article><h3>Сильная сторона</h3><ul>{_items(data.get('amplified'))}</ul></article>
          <article><h3>Зона внимания</h3><ul>{_items(data.get('risks'), 3)}</ul></article>
          <article><h3>Что помогает</h3><ul>{_items(data.get('actions'))}</ul></article>
        </div>
        <aside class="visual-card"><div class="score">{score}<small>/10</small></div>{visual_html}</aside>
      </div>
      <footer class="basis"><b>Астрологическое основание</b><ul>{_items(data.get('astro_basis'))}</ul></footer>
    </section>"""


def render_natal_html(report: dict) -> str:
    cover = report.get("cover") or {}
    theme = report.get("main_theme") or {}
    temperament = report.get("temperament") or {}
    signature = report.get("signature") or {}
    risks = report.get("risk_summary") or []
    opportunities = report.get("opportunities") or []
    plan = report.get("plan") or []
    chart_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "chart-wheel.jpg")
    chart_uri = ""
    if os.path.exists(chart_path):
        import base64
        chart_uri = "data:image/jpeg;base64," + base64.b64encode(open(chart_path, "rb").read()).decode()

    planets = "".join(
        f'<article><span>{_safe(item.get("label"))}</span><b>{_safe(item.get("value"))}</b><small>{_safe(item.get("meaning"))}</small></article>'
        for item in (temperament.get("planets") or [])[:6]
    )
    risk_cards = "".join(
        f'<article class="risk"><span>{_safe(item.get("title"))}</span><b>{_score(item.get("level"))}/10</b><p>{_safe(item.get("risk"))}</p><small>{_safe(item.get("support"))}</small></article>'
        for item in risks[:4]
    )
    opportunity_cards = "".join(
        f'<article><span>{index:02d}</span><h3>{_safe(item.get("title"))}</h3><p>{_safe(item.get("text"))}</p></article>'
        for index, item in enumerate(opportunities[:4], 1)
    )
    plan_rows = "".join(
        f'<article><b>{_safe(item.get("step"), index)}</b><p>{_safe(item.get("action"))}</p></article>'
        for index, item in enumerate(plan[:5], 1)
    )

    body = f"""
    <section class="page cover"><div class="cover-copy"><span>НАТАЛЬНАЯ КАРТА · ЛИЧНЫЙ РАЗБОР</span><h1>{_safe(cover.get('title'), 'Натальная карта')}</h1><h2>{_safe(theme.get('title'))}</h2><p>{_safe(cover.get('subtitle'))}</p><div class="cover-meta"><b>{_safe(cover.get('birth_data'))}</b><b>{_safe(cover.get('dominant'))}</b></div></div><div class="wheel">{f'<img src="{chart_uri}">' if chart_uri else ''}</div></section>
    <section class="page"><header class="section-head"><span>— — 01 · БАЗОВЫЙ ТЕМПЕРАМЕНТ</span><small>Из чего собран характер и что задаёт внутренний ритм.</small></header><article class="hero-text"><h2>{_safe(temperament.get('title'), theme.get('title'))}</h2><p>{_safe(temperament.get('text'), theme.get('text'))}</p></article><div class="planet-grid">{planets}</div></section>
    <section class="page"><header class="section-head"><span>— — 02 · СТИХИИ И КАЧЕСТВА</span><small>Как распределяется энергия карты.</small></header><div class="temper-grid"><div class="chart-card">{_radar((temperament.get('elements') or []) + (temperament.get('qualities') or []))}</div><div><h2>{_safe(temperament.get('balance_title'), 'Внутренний баланс')}</h2><p>{_safe(temperament.get('balance_text'))}</p><div class="bars">{_bars(temperament.get('elements'), ['Огонь','Земля','Воздух','Вода'])}</div></div></div></section>
    {_section_page(3, 'mind', report, 'Как вы думаете, говорите и принимаете решения.', 'bars')}
    {_section_page(4, 'identity', report, 'Как вас видят снаружи и что происходит внутри.', 'orbit')}
    {_section_page(5, 'emotions', report, 'Что создаёт безопасность и как проживаются чувства.', 'bars')}
    {_section_page(6, 'relationships', report, 'Как вы любите, сближаетесь и сохраняете границы.', 'orbit')}
    {_section_page(7, 'energy', report, 'Воля, темп, действие и способность восстанавливаться.', 'battery')}
    {_section_page(8, 'career', report, 'Деньги, профессиональный вектор и способ реализации.', 'bars')}
    {_section_page(9, 'talents', report, 'То, что уже работает как естественный ресурс.', 'orbit')}
    {_section_page(10, 'growth', report, 'Сценарии взросления и точки глубокой перестройки.', 'bars')}
    <section class="page"><header class="section-head"><span>— — 11 · РИСКИ И СЛЕПЫЕ ЗОНЫ</span><small>Не приговор, а карта бережного внимания.</small></header><div class="risk-grid">{risk_cards}</div></section>
    <section class="page"><header class="section-head"><span>— — 12 · ГЛАВНЫЕ РЕСУРСЫ</span><small>На что можно уверенно опираться.</small></header><div class="opportunity-grid">{opportunity_cards}</div></section>
    <section class="page"><header class="section-head"><span>— — 13 · ПРАКТИКА И РЕШЕНИЯ</span><small>Как переводить карту в ежедневные действия.</small></header><div class="plan-list">{plan_rows}</div></section>
    <section class="page final"><header class="section-head"><span>— — 14 · ИТОГ</span><small>Не меняться, а научиться собой управлять.</small></header><article class="final-card"><h2>{_safe(signature.get('title'), 'Формула личности')}</h2><p>{_safe(signature.get('final_formula'), report.get('final_formula'))}</p><div class="final-columns"><div><b>Доминанты</b><ul>{_items(signature.get('elements'))}</ul></div><div><b>Ключевые положения</b><ul>{_items(signature.get('positions'))}</ul></div><div><b>Ключевые аспекты</b><ul>{_items(signature.get('aspects'))}</ul></div></div></article></section>
    """
    return f"""<!doctype html><html lang="ru"><head><meta charset="utf-8"><style>
    @page{{size:A4;margin:0}}*{{box-sizing:border-box}}body{{margin:0;background:#09091f;color:#e8e5ef;font-family:Manrope,Arial,sans-serif}}h1,h2,h3{{font-family:'Cormorant Garamond',Georgia,serif;font-weight:500}}.page{{width:210mm;height:297mm;padding:18mm;page-break-after:always;overflow:hidden;background:radial-gradient(circle at 88% 12%,rgba(55,48,124,.24),transparent 35%),linear-gradient(180deg,#0a0a25,#09091f)}}.cover{{display:grid;grid-template-columns:1.1fr .9fr;gap:10mm;align-items:center}}.cover-copy>span,.section-head span{{color:#d8ad52;font-size:8px;font-weight:800;letter-spacing:3px}}.cover h1{{margin:5mm 0 2mm;color:#d8ad52;font-size:44px;line-height:1}}.cover h2{{margin:0 0 7mm;color:#f3efe4;font-size:26px}}.cover p,.section-head small,.hero-text p,.temper-grid p{{color:#aaa5b7;line-height:1.6}}.cover-meta{{display:grid;gap:3mm;margin-top:12mm}}.cover-meta b{{padding:4mm 0;border-top:1px solid rgba(216,173,82,.24);font-size:11px}}.wheel img{{width:100%;border-radius:7mm;border:1px solid rgba(216,173,82,.3)}}.section-head{{padding-bottom:7mm;border-bottom:1px solid rgba(216,173,82,.14)}}.section-head small{{display:block;margin-top:4mm;font-size:11px}}.hero-text,.lead-card,.chart-card,.visual-card,.basis,.final-card{{margin-top:12mm;padding:9mm;border:1px solid rgba(136,126,184,.18);border-radius:6mm;background:linear-gradient(135deg,rgba(32,31,70,.92),rgba(19,19,51,.9))}}.hero-text h2,.lead-card h2,.temper-grid h2,.final-card h2{{margin:0 0 5mm;color:#f2eee5;font-size:30px}}.hero-text p,.lead-card p{{font-size:12px;line-height:1.65;color:#b9b4c4}}.planet-grid,.copy-cards,.risk-grid,.opportunity-grid{{display:grid;grid-template-columns:1fr 1fr;gap:5mm;margin-top:8mm}}.planet-grid article,.copy-cards article,.risk-grid article,.opportunity-grid article{{padding:6mm;border:1px solid rgba(136,126,184,.16);border-radius:5mm;background:rgba(24,24,57,.78)}}.planet-grid span,.copy-cards h3,.risk span,.opportunity-grid span,.basis b,.final-columns b{{color:#d8ad52;font-size:9px;letter-spacing:1.5px;text-transform:uppercase}}.planet-grid b{{display:block;margin:2mm 0;color:#f1ede5;font-size:15px}}.planet-grid small,.risk small{{color:#77738b;font-size:9px}}.temper-grid,.section-grid{{display:grid;grid-template-columns:1.08fr .92fr;gap:8mm;margin-top:10mm}}.chart-card{{margin-top:0;display:grid;place-items:center}}.radar{{width:90mm;height:90mm}}.grid polygon,.grid line{{fill:none;stroke:rgba(216,173,82,.20)}}.area{{fill:rgba(216,173,82,.13)}}.line{{fill:none;stroke:#d8ad52;stroke-width:2}}.radar text{{fill:#aaa5b7;font-size:9px}}.bars{{display:grid;gap:5mm;margin-top:9mm}}.bar{{display:grid;grid-template-columns:24mm 1fr 12mm;gap:3mm;align-items:center;font-size:9px}}.bar i{{height:2mm;border-radius:9px;background:#242442;overflow:hidden}}.bar i b{{display:block;height:100%;background:#d8ad52}}.bar em{{color:#d8ad52;font-style:normal}}.lead-card{{margin-top:8mm}}.lead-card h2{{font-size:25px}}.lead-card p{{margin:0}}.copy-cards{{margin-top:0}}.copy-cards h3{{margin:0 0 3mm}}ul{{margin:0;padding-left:4mm}}li{{margin-bottom:2mm;color:#aaa6b6;font-size:10px;line-height:1.45}}.visual-card{{margin-top:0;min-height:112mm}}.score{{color:#d8ad52;font-size:24px}}.score small{{color:#716b88;font-size:13px}}.orbit{{height:74mm;position:relative;display:grid;place-items:center}}.orbit i{{position:absolute;width:48mm;height:48mm;border:1px solid #d8ad52;border-radius:50%;box-shadow:0 0 30px rgba(73,64,151,.35)}}.orbit b{{z-index:2;color:#d8ad52}}.orbit span{{position:absolute;padding:1mm 2mm;border-radius:9px;background:#171733;color:#aaa5b7;font-size:8px}}.orbit span:nth-of-type(1){{top:7mm}}.orbit span:nth-of-type(2){{bottom:6mm;left:4mm}}.orbit span:nth-of-type(3){{bottom:6mm;right:4mm}}.battery{{height:30mm;margin-top:17mm;padding:2mm;border:1.5px solid #d8ad52;border-radius:4mm}}.battery div{{height:100%;display:grid;place-items:center;border-radius:2mm;background:linear-gradient(90deg,#5144b8,#d8ad52);color:#0a0a25;font-weight:800}}.battery-labels{{display:flex;justify-content:space-between;margin-top:3mm;color:#77738b;font-size:8px}}.basis{{margin-top:6mm;padding:5mm}}.basis ul{{display:grid;grid-template-columns:1fr 1fr;gap:2mm 5mm;margin-top:3mm}}.risk-grid,.opportunity-grid{{margin-top:12mm}}.risk-grid article,.opportunity-grid article{{min-height:72mm;background:linear-gradient(135deg,rgba(34,32,76,.92),rgba(17,17,46,.9))}}.risk b{{float:right;color:#d8ad52}}.risk p,.opportunity-grid p{{color:#b2adbd;font-size:11px;line-height:1.55}}.risk small{{display:block;border-top:1px solid rgba(216,173,82,.18);padding-top:3mm}}.opportunity-grid h3{{color:#f0ece3;font-size:22px}}.plan-list{{display:grid;gap:5mm;margin-top:12mm}}.plan-list article{{display:grid;grid-template-columns:13mm 1fr;align-items:center;padding:6mm;border:1px solid rgba(136,126,184,.16);border-radius:5mm;background:#171733}}.plan-list b{{width:9mm;height:9mm;display:grid;place-items:center;border-radius:50%;background:#d8ad52;color:#09091f}}.plan-list p{{margin:0;color:#bbb6c5}}.final-card{{margin-top:18mm}}.final-card>p{{font-family:Georgia,serif;color:#d8ad52;font-size:22px;line-height:1.45}}.final-columns{{display:grid;grid-template-columns:repeat(3,1fr);gap:5mm;margin-top:10mm}}.final-columns>div{{padding:5mm;border-top:1px solid rgba(216,173,82,.3)}}
    </style></head><body>{body}</body></html>"""


def _render_natal_editorial_html_legacy(report: dict) -> str:
    """Continuous editorial layout matching the approved Lovable /natal page."""
    cover = report.get("cover") or {}
    theme = report.get("main_theme") or {}
    temperament = report.get("temperament") or {}
    signature = report.get("signature") or {}

    def paragraphs(values, fallback: str = "") -> str:
        source = values if isinstance(values, list) and values else [fallback]
        return "".join(f"<p>{_safe(value)}</p>" for value in source if value)

    def compact_cards(category: dict) -> str:
        cards = [
            ("Сильная сторона", category.get("amplified")),
            ("Зона внимания", category.get("risks")),
            ("Что помогает", category.get("actions")),
        ]
        return "".join(
            f'<article><h4>{title}</h4><ul>{_items(items, 4)}</ul></article>'
            for title, items in cards
        )

    def category_section(number: int, key: str, subtitle: str, visual: str = "") -> str:
        category = _category(report, key)
        score = _score(category.get("score"), 7)
        keywords = list(category.get("keywords") or ["смысл", "опора", "вектор"])
        visual_html = ""
        if visual == "bars":
            visual_html = f'<div class="inline-visual"><div class="score-big">{score}<small>/10</small></div>{_bars([{"name": name, "value": max(1, score-index)} for index, name in enumerate(keywords[:3])], keywords[:3])}</div>'
        elif visual == "battery":
            visual_html = f'<div class="inline-visual"><div class="battery"><div style="width:{score*10}%"><span>{score}/10</span></div></div></div>'
        elif visual == "orbit":
            visual_html = f'<div class="inline-visual"><div class="mini-orbit"><i></i><b>{_safe(category.get("title"))}</b></div></div>'
        return f"""
        <section class="report-section">
          <header><span>— — {number:02d} · {_safe(category.get('title'), key)}</span><small>{_safe(subtitle)}</small></header>
          <div class="prose">{paragraphs(category.get('analysis'), category.get('summary'))}</div>
          {visual_html}
          <div class="feature"><h3>{_safe(category.get('main_takeaway'), category.get('title'))}</h3><p>{_safe(category.get('summary'))}</p></div>
          <div class="mini-grid">{compact_cards(category)}</div>
          <div class="astro"><b>Астрологическое основание</b><ul>{_items(category.get('astro_basis'), 4)}</ul></div>
        </section>"""

    planet_rows = "".join(
        f'<div class="planet-row"><span>{_safe(item.get("label"))}</span><b>{_safe(item.get("value"))}</b><em>{_safe(item.get("meaning"))}</em></div>'
        for item in (temperament.get("planets") or [])[:6]
    )
    risks = "".join(
        f'<article><div><span>{_safe(item.get("title"))}</span><b>{_score(item.get("level"))}/10</b></div><p>{_safe(item.get("risk"))}</p><small>{_safe(item.get("support"))}</small></article>'
        for item in (report.get("risk_summary") or [])[:4]
    )
    resources = "".join(
        f'<article><span>{index:02d}</span><h3>{_safe(item.get("title"))}</h3><p>{_safe(item.get("text"))}</p></article>'
        for index, item in enumerate((report.get("opportunities") or [])[:4], 1)
    )
    plan = "".join(
        f'<article><b>{_safe(item.get("step"), index)}</b><p>{_safe(item.get("action"))}</p></article>'
        for index, item in enumerate((report.get("plan") or [])[:5], 1)
    )
    final_columns = "".join(
        f'<div><b>{title}</b><ul>{_items(signature.get(key), 4)}</ul></div>'
        for title, key in [("Доминанты", "elements"), ("Положения", "positions"), ("Аспекты", "aspects")]
    )

    body = f"""
    <main class="report">
      <section class="intro">
        <span class="eyebrow">НАТАЛЬНАЯ КАРТА · ЛИЧНЫЙ РАЗБОР</span>
        <h1>{_safe(cover.get('title'), 'Натальная карта')}</h1>
        <h2>{_safe(theme.get('title'))}</h2>
        <p>{_safe(theme.get('text'), cover.get('subtitle'))}</p>
        <div class="intro-meta"><span>{_safe(cover.get('birth_data'))}</span><span>{_safe(cover.get('dominant'))}</span></div>
        <div class="planet-list">{planet_rows}</div>
      </section>
      <section class="report-section temperament">
        <header><span>— — 01 · БАЗОВЫЙ ТЕМПЕРАМЕНТ</span><small>Из чего собран характер и что задаёт внутренний ритм.</small></header>
        <div class="prose"><h3>{_safe(temperament.get('title'))}</h3><p>{_safe(temperament.get('text'))}</p></div>
        <div class="temper-layout"><div>{_radar((temperament.get('elements') or []) + (temperament.get('qualities') or []))}</div><aside><h3>{_safe(temperament.get('balance_title'))}</h3><p>{_safe(temperament.get('balance_text'))}</p>{_bars(temperament.get('elements'), ['Огонь','Земля','Воздух','Вода'])}</aside></div>
      </section>
      {category_section(2, 'mind', 'Как вы думаете, говорите и принимаете решения.', 'bars')}
      {category_section(3, 'identity', 'Как вас видят снаружи и что происходит внутри.', 'orbit')}
      {category_section(4, 'emotions', 'Что создаёт безопасность и как проживаются чувства.', 'bars')}
      {category_section(5, 'relationships', 'Как вы любите, сближаетесь и сохраняете границы.', 'orbit')}
      {category_section(6, 'energy', 'Воля, действие и способность восстанавливаться.', 'battery')}
      {category_section(7, 'career', 'Деньги, профессиональный вектор и реализация.', 'bars')}
      {category_section(8, 'talents', 'То, что уже работает как естественный ресурс.', 'orbit')}
      {category_section(9, 'growth', 'Сценарии взросления и точки перестройки.', 'bars')}
      <section class="report-section"><header><span>— — 10 · РИСКИ И СЛЕПЫЕ ЗОНЫ</span><small>Не приговор, а карта бережного внимания.</small></header><div class="risk-list">{risks}</div></section>
      <section class="report-section"><header><span>— — 11 · ГЛАВНЫЕ РЕСУРСЫ</span><small>На что можно уверенно опираться.</small></header><div class="resource-list">{resources}</div></section>
      <section class="report-section"><header><span>— — 12 · ПРАКТИКА И РЕШЕНИЯ</span><small>Как переводить карту в ежедневные действия.</small></header><div class="plan-list">{plan}</div></section>
      <section class="report-section conclusion"><header><span>— — 13 · ИТОГ</span><small>Не меняться, а научиться собой управлять.</small></header><div class="final-card"><h2>{_safe(signature.get('title'))}</h2><p>{_safe(signature.get('final_formula'), report.get('final_formula'))}</p><div class="final-columns">{final_columns}</div></div></section>
    </main>"""
    return f"""<!doctype html><html lang="ru"><head><meta charset="utf-8"><style>
    @page{{size:A4;margin:16mm 21mm 18mm}}*{{box-sizing:border-box}}html,body{{margin:0;background:#0b0b2a;color:#aaa6b8;font-family:Manrope,Arial,sans-serif;font-size:11.2px;line-height:1.68}}body{{background:linear-gradient(180deg,#0b0b2a,#0a0a25)}}h1,h2,h3{{font-family:'Cormorant Garamond',Georgia,serif;font-weight:500}}.report{{width:100%}}.intro{{padding:8mm 0 18mm}}.eyebrow,.report-section header span{{color:#cda64e;font-size:7px;font-weight:800;letter-spacing:2.7px}}.intro h1{{margin:4mm 0 1mm;color:#d2a94f;font-size:32px;line-height:1}}.intro h2{{margin:0 0 5mm;color:#eee9df;font-size:20px}}.intro>p{{max-width:155mm;font-family:Georgia,serif;color:#b9b4c2;font-size:11px}}.intro-meta{{display:flex;gap:10mm;padding:5mm 0;border-bottom:1px solid rgba(205,166,78,.12);color:#d2a94f;font-size:8px}}.planet-list{{display:grid;grid-template-columns:1fr 1fr;gap:0 8mm;margin-top:7mm}}.planet-row{{display:grid;grid-template-columns:26mm 1fr;gap:2mm;padding:3mm 0;border-bottom:1px solid rgba(255,255,255,.045)}}.planet-row span{{color:#76728a;font-size:7px;text-transform:uppercase;letter-spacing:1.2px}}.planet-row b{{color:#d2a94f;font-size:9px}}.planet-row em{{grid-column:2;color:#77738a;font-size:7.5px;font-style:normal}}.report-section{{padding:15.5mm 0 6mm;break-inside:auto}}.report-section header{{padding-bottom:5mm;border-bottom:1px solid rgba(205,166,78,.10)}}.report-section header small{{display:block;margin-top:2mm;color:#77738b;font-size:8px}}.prose{{margin-top:6mm}}.prose h3{{color:#e8e3dc;font-size:18px}}.prose p{{margin:0 0 4.5mm;color:#aaa6b8}}.feature,.inline-visual,.astro,.mini-grid article,.risk-list article,.resource-list article,.plan-list article,.final-card{{border:1px solid rgba(128,121,174,.12);border-radius:4mm;background:#151534}}.feature{{margin:6mm 0;padding:6mm 7mm;break-inside:avoid}}.feature h3{{margin:0 0 3mm;color:#e8e3dc;font-size:18px}}.feature p{{margin:0;color:#aaa6b8}}.inline-visual{{margin:6mm 0;padding:7mm;break-inside:avoid}}.score-big{{color:#d2a94f;font-size:22px}}.score-big small{{color:#6f6b83;font-size:10px}}.bars{{display:grid;gap:3mm;margin-top:4mm}}.bar{{display:grid;grid-template-columns:28mm 1fr 12mm;gap:3mm;align-items:center;font-size:8px}}.bar i{{height:1.4mm;background:#232343;overflow:hidden}}.bar i b{{display:block;height:100%;background:#cda64e}}.bar em{{color:#cda64e;font-style:normal}}.mini-orbit{{height:42mm;display:grid;place-items:center;position:relative}}.mini-orbit i{{position:absolute;width:34mm;height:34mm;border:1px solid #cda64e;border-radius:50%}}.mini-orbit b{{z-index:2;color:#cda64e}}.battery{{height:18mm;padding:1.5mm;border:1px solid #cda64e;border-radius:3mm}}.battery div{{height:100%;display:grid;place-items:center;background:linear-gradient(90deg,#4c43a8,#cda64e);color:#0b0b2a;font-weight:800}}.mini-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:3mm;margin:5mm 0;break-inside:avoid}}.mini-grid article{{padding:4mm}}.mini-grid h4,.astro b,.risk-list span,.resource-list>article>span,.final-columns b{{margin:0 0 2mm;color:#cda64e;font-size:7px;letter-spacing:1.2px;text-transform:uppercase}}ul{{margin:0;padding-left:3mm}}li{{margin-bottom:1.5mm;color:#8f8a9e;font-size:8px}}.astro{{padding:4mm;break-inside:avoid}}.astro ul{{display:grid;grid-template-columns:1fr 1fr;gap:1mm 4mm;margin-top:2mm}}.temper-layout{{display:grid;grid-template-columns:1fr 1fr;gap:7mm;align-items:center;margin:6mm 0;break-inside:avoid}}.temper-layout>div{{padding:5mm;border:1px solid rgba(128,121,174,.12);border-radius:4mm;background:#151534}}.temper-layout .radar{{width:70mm;height:70mm}}.grid polygon,.grid line{{fill:none;stroke:rgba(205,166,78,.18)}}.area{{fill:rgba(205,166,78,.10)}}.line{{fill:none;stroke:#cda64e;stroke-width:2}}.radar text{{fill:#77738b;font-size:8px}}.temper-layout aside h3{{color:#e8e3dc;font-size:18px}}.risk-list,.resource-list,.plan-list{{display:grid;gap:3mm;margin-top:6mm}}.risk-list article,.resource-list article{{padding:5mm;break-inside:avoid}}.risk-list article div{{display:flex;justify-content:space-between}}.risk-list b{{color:#cda64e}}.risk-list p,.resource-list p{{margin:2mm 0}}.risk-list small{{display:block;padding-top:2mm;border-top:1px solid rgba(205,166,78,.12);color:#77738b}}.resource-list{{grid-template-columns:1fr 1fr}}.resource-list article h3{{color:#e8e3dc;font-size:16px}}.plan-list article{{display:grid;grid-template-columns:9mm 1fr;align-items:center;padding:4mm;break-inside:avoid}}.plan-list article b{{width:7mm;height:7mm;display:grid;place-items:center;border-radius:50%;background:#cda64e;color:#0b0b2a}}.plan-list article p{{margin:0}}.final-card{{margin-top:8mm;padding:8mm;break-inside:avoid}}.final-card h2{{color:#e8e3dc;font-size:22px}}.final-card>p{{font-family:Georgia,serif;color:#cda64e;font-size:14px;line-height:1.5}}.final-columns{{display:grid;grid-template-columns:repeat(3,1fr);gap:4mm;margin-top:6mm}}.final-columns>div{{padding-top:3mm;border-top:1px solid rgba(205,166,78,.18)}}
    @page{{background:#0b0b2a}}
    .report-section header{{break-after:avoid}}
    .prose h3{{break-after:avoid;margin:0 0 3mm}}
    .feature{{border:0;border-left:1px solid rgba(205,166,78,.38);border-radius:0;background:rgba(21,21,52,.34);padding:4mm 5mm}}
    .inline-visual{{border:0;border-radius:0;background:transparent;padding:3mm 0}}
    .mini-grid{{break-inside:auto;gap:5mm}}
    .mini-grid article{{border:0;border-top:1px solid rgba(205,166,78,.16);border-radius:0;background:transparent;padding:3mm 0}}
    .astro{{border:0;border-radius:0;background:transparent;padding:3mm 0;border-top:1px solid rgba(205,166,78,.10)}}
    .temper-layout>div{{border:0;border-radius:0;background:transparent;padding:2mm}}
    .risk-list article,.resource-list article{{border-color:rgba(205,166,78,.10);background:rgba(21,21,52,.42)}}
    .conclusion{{min-height:245mm;display:flex;flex-direction:column;justify-content:center}}
    </style></head><body>{body}</body></html>"""


def render_natal_editorial_html(report: dict) -> str:
    """Natal report markup copied from the layout rhythm shown in the reference video."""
    cover = report.get("cover") or {}
    theme = report.get("main_theme") or {}
    temperament = report.get("temperament") or {}
    categories = {item.get("key"): item for item in report.get("categories") or []}
    signature = report.get("signature") or {}
    person_name = _safe(cover.get("person_name")) or _safe(cover.get("title")).replace("Натальная карта", "").strip() or "Анна"

    def section_head(number: int, title: str, subtitle: str) -> str:
        return f'''<header class="section-head"><div><i></i><span>— {number:02d} · {_safe(title).upper()}</span></div><p>{_safe(subtitle)}</p></header>'''

    def prose(values, fallback="") -> str:
        parts = values if isinstance(values, list) and values else [fallback]
        text = " ".join(_safe(value).strip() for value in parts if value)
        return f"<p>{text}</p>" if text else ""

    def key_cards() -> str:
        planets = temperament.get("planets") or []
        wanted = [("СОЛНЦЕ", 0), ("ЛУНА", 2), ("АСЦЕНДЕНТ", 1), ("MC", 3)]
        cards = []
        for label, index in wanted:
            item = planets[index] if index < len(planets) else {}
            cards.append(f'<article><b>{label}</b><span>{_safe(item.get("value"), "—")}</span></article>')
        return "".join(cards)

    def sphere_rows() -> str:
        labels = [
            ("identity", "Глубина и проницательность"),
            ("mind", "Ум и анализ"),
            ("emotions", "Эмоциональная устойчивость"),
            ("relationships", "Любовь и близость"),
            ("energy", "Воля и действие"),
            ("career", "Деньги и реализация"),
            ("growth", "Границы и защита себя"),
        ]
        return "".join(
            f'<div class="sphere-row"><span>{label}</span><b>{_score((categories.get(key) or {}).get("score"), 7)}<small>/10</small></b></div>'
            for key, label in labels
        )

    def planet_rows() -> str:
        return "".join(
            f'''<article class="planet-line"><h3>{_safe(item.get("label"))}</h3><b>{_safe(item.get("value"))}</b><span>{_safe(item.get("house"), "—")}</span><p>{_safe(item.get("meaning"))}</p></article>'''
            for item in (temperament.get("planets") or [])
        )

    def factor_card(category: dict, index: int) -> str:
        basis = category.get("astro_basis") or []
        title = basis[index] if index < len(basis) else category.get("main_takeaway")
        return f'''<article class="factor"><div><b>ФАКТОР</b><small>{_safe((category.get("keywords") or ["аспект"])[0]).upper()}</small></div><h3>{_safe(title)}</h3><p>{_safe(category.get("summary"))}</p><footer>ПОЧЕМУ ТАК · {_safe(title)}</footer></article>'''

    def scale_card(category: dict, title: str) -> str:
        score = _score(category.get("score"), 7)
        labels = list(category.get("keywords") or ["Глубина", "Устойчивость", "Свобода"])
        rows = "".join(
            f'<div class="scale-row"><div><span>{_safe(label)}</span><b>{max(1, score-i)}<small>/10</small></b></div><i><em style="width:{max(1, score-i)*10}%"></em></i></div>'
            for i, label in enumerate(labels[:3])
        )
        return f'<article class="scale-card"><b>{_safe(title).upper()}</b>{rows}</article>'

    def narrative_section(number: int, key: str, title: str, subtitle: str, scale_title: str) -> str:
        category = categories.get(key) or {}
        analysis = category.get("analysis") or []
        quote = category.get("main_takeaway") or category.get("summary")
        return f'''<section class="report-section narrative">
          {section_head(number, title, subtitle)}
          <article class="story-card"><h2>{_safe(category.get("title"), title)}</h2>{prose(analysis, category.get("summary"))}<blockquote>{_safe(quote)}</blockquote></article>
          {factor_card(category, 0)}
          {scale_card(category, scale_title)}
        </section>'''

    risk_rows = "".join(
        f'<article><b>{index:02d}</b><div><h3>{_safe(item.get("title"))}</h3><p>{_safe(item.get("risk"))}</p><small>{_safe(item.get("support"))}</small></div></article>'
        for index, item in enumerate(report.get("risk_summary") or [], 1)
    )
    resources = "".join(
        f'<article><b>{_safe(item.get("title")).upper()}</b><small>{index:02d}</small><p>{_safe(item.get("text"))}</p></article>'
        for index, item in enumerate(report.get("opportunities") or [], 1)
    )
    plan = "".join(
        f'<article><b>{index:02d}</b><div><h3>{_safe(item.get("title"), item.get("action"))}</h3><p>{_safe(item.get("action"))}</p><small>{_safe(item.get("basis"))}</small></div></article>'
        for index, item in enumerate(report.get("plan") or [], 1)
    )
    final_text = signature.get("final_formula") or report.get("final_formula")

    body = f'''<main class="natal-report">
      <section class="intro">
        <div class="eyebrow"><i></i><span>НАТАЛЬНАЯ КАРТА · ЛИЧНЫЙ РАЗБОР</span></div>
        <h1><em>Натальная карта</em><span>{person_name}</span></h1>
        <h2>{_safe(cover.get("subtitle"), "Разбор личности по характеру, эмоциям, мышлению, любви, энергии и реализации.")}</h2>
        <p>{_safe(theme.get("text"))}</p>
        <dl><dt>ФОРМУЛА ЛИЧНОСТИ</dt><dd>{_safe(theme.get("title"))}</dd><p>{_safe(temperament.get("text"))}</p><dt>ГЛАВНОЕ НАПРЯЖЕНИЕ</dt><dd>{_safe(temperament.get("balance_title"))}</dd><p>{_safe(temperament.get("balance_text"))}</p><dt>ГЛАВНЫЙ РЕСУРС</dt><dd>{_safe((categories.get("talents") or {}).get("main_takeaway"))}</dd><dt>ГЛАВНЫЙ РИСК</dt><dd>{_safe((categories.get("growth") or {}).get("main_takeaway"))}</dd></dl>
        <div class="key-grid">{key_cards()}</div>
      </section>
      <section class="report-section wheel-section">
        {section_head(2, "Быстрая карта личности", "Одна картинка: где вы сильны по природе, а где ресурс приходится добирать усилием. Провалы — не диагноз, а адрес для внимания.")}
        <article class="wheel-card"><h2>Колесо сфер</h2><p>Чем ближе к краю — тем ярче сфера проявлена от рождения. Низкие оси означают, что тема требует сознательной работы, а не что она недоступна.</p><div class="sphere-list">{sphere_rows()}</div><div class="radar-wrap">{_radar([{"name": key, "value": _score((categories.get(key) or {}).get("score"), 7)} for key in ["identity","mind","emotions","relationships","energy","career","growth"]])}</div><div class="wheel-notes"><article><b>ЧТО ВИДНО СРАЗУ</b><p>{_safe((categories.get("identity") or {}).get("main_takeaway"))}</p></article><article><b>КУДА СМОТРЕТЬ</b><p>{_safe((categories.get("growth") or {}).get("main_takeaway"))}</p></article><article><b>ОСЬ РОСТА</b><p>{_safe((categories.get("growth") or {}).get("summary"))}</p></article></div></article>
      </section>
      <section class="report-section planets">{section_head(3, "Из чего собрана карта", "Справочный блок: ключевые точки карты и их человеческий смысл.")}<div class="planet-table">{planet_rows()}</div></section>
      {narrative_section(4, "identity", "Характер и способ проявляться", "Как вас видят снаружи и что происходит внутри в это же время.", "Шкалы характера")}
      {narrative_section(5, "emotions", "Эмоции и внутренние потребности", "Что даёт ощущение безопасности и почему чувства иногда качает.", "Шкалы эмоциональной сферы")}
      {narrative_section(6, "mind", "Мышление и коммуникация", "Как вы думаете, говорите и считываете скрытые смыслы.", "Шкалы мышления")}
      {narrative_section(7, "relationships", "Любовь и отношения", "Что вам нужно в близости, почему это трудно совместить и какой партнёр подходит.", "Шкалы близости")}
      {narrative_section(8, "energy", "Энергия, воля и границы", "Как вы действуете, защищаете себя и восстанавливаете силы.", "Шкалы энергии")}
      {narrative_section(9, "career", "Деньги и реализация", "Как устроены деньги, работа и профессиональный путь.", "Шкалы реализации")}
      <section class="report-section resources">{section_head(10, "Сильные стороны", "Сферы, в которых карта уже даёт естественную опору.")}<div class="resource-grid">{resources}</div></section>
      <section class="report-section risks">{section_head(11, "Зоны роста", "То, что требует внимания, практики и более бережной стратегии.")}<div class="number-list">{risk_rows}</div></section>
      <section class="report-section practice">{section_head(12, "Практические рекомендации", "Не абстрактные советы, а конкретные способы обращаться со своей картой.")}<div class="number-list">{plan}</div></section>
      <section class="report-section final">{section_head(13, "Итог", "")}<article><h2>{_safe(signature.get("title"), "Не меняться, а научиться собой управлять")}</h2><p>{_safe(final_text)}</p><blockquote>{_safe(theme.get("text"))}</blockquote><footer><i></i><b>КОНЕЦ РАЗБОРА</b></footer></article></section>
    </main>'''

    return f'''<!doctype html><html lang="ru"><head><meta charset="utf-8"><style>
    @page{{size:A4;margin:0;background:#0b0a2a}}*{{box-sizing:border-box}}html,body{{margin:0;background:#0b0a2a;color:#aaa6b8;font-family:Arial,sans-serif;font-size:14px;line-height:1.56}}body{{background:#0b0a2a}}h1,h2,h3,dd,blockquote{{font-family:Georgia,serif;font-weight:400}}.natal-report{{width:100%;padding:11mm 8mm 18mm;background:#0b0a2a}}.intro,.report-section{{max-width:100%;margin:0 auto}}.eyebrow,.section-head>div{{display:flex;align-items:center;gap:4mm;color:#d3a840;font-size:9px;font-weight:700;letter-spacing:2.1px}}.eyebrow i,.section-head i,.final footer i{{display:block;width:8mm;height:1px;background:#d3a840}}.intro{{padding:0 0 18mm}}.intro h1{{margin:10mm 0 5mm;font-size:46px;line-height:1.08}}.intro h1 em{{display:block;color:#d3a840;font-weight:400}}.intro h1 span{{display:block;color:#eee8df}}.intro h2{{margin:0 0 8mm;color:#817d90;font:italic 16px Georgia,serif}}.intro>p{{max-width:172mm;margin:0 0 12mm;color:#aaa6b8}}dl{{margin:0}}dt{{margin-top:7mm;color:#d3a840;font-size:9px;font-weight:700;letter-spacing:1.8px}}dd{{margin:2mm 0 1mm;color:#d7d1d0;font-size:20px}}dl p{{margin:0;color:#898596;font-size:13px}}.key-grid{{display:grid;grid-template-columns:1fr 1fr;gap:4mm;margin-top:10mm}}.key-grid article{{padding:5mm;text-align:center;border:1px solid #24223f;border-radius:6mm;background:#12112f}}.key-grid b{{display:block;color:#d3a840;font-size:9px;letter-spacing:1.5px}}.key-grid span{{display:block;margin-top:2mm;color:#d3a840;font:18px Georgia,serif}}.report-section{{padding:14mm 0 10mm}}.section-head{{margin-bottom:8mm}}.section-head p{{margin:3mm 0 0;color:#7f7b8e;font-size:13px}}.wheel-card,.story-card,.factor,.scale-card,.final>article,.resource-grid article,.number-list{{border:1px solid #272542;border-radius:6mm;background:#151433}}.wheel-card{{padding:7mm}}.wheel-card h2,.story-card h2,.final h2{{margin:0 0 4mm;color:#e4ded8;font-size:26px}}.wheel-card>p{{margin:0 0 7mm;color:#918d9e;font-size:13px}}.sphere-row{{display:flex;justify-content:space-between;padding:3mm 0;border-bottom:1px solid #25233e}}.sphere-row b,.scale-row b{{color:#d3a840;font:16px Georgia,serif}}.sphere-row small,.scale-row small{{color:#5f5b70;font-size:10px}}.radar-wrap{{display:grid;place-items:center;padding:7mm 0}}.radar-wrap .radar{{width:105mm;height:105mm}}.grid polygon,.grid line{{fill:none;stroke:#272541}}.area{{fill:rgba(211,168,64,.15)}}.line{{fill:none;stroke:#d3a840;stroke-width:2}}.radar text{{fill:#aaa6b8;font-size:7px}}.wheel-notes{{display:grid;gap:4mm}}.wheel-notes article{{padding:5mm;border:1px solid #292742;border-radius:6mm;background:#181735}}.wheel-notes b,.scale-card>b,.factor b,.resource-grid b{{color:#d3a840;font-size:9px;letter-spacing:1.7px}}.wheel-notes p{{margin:2mm 0 0}}.planet-table{{border:1px solid #262440;border-radius:6mm;overflow:hidden;background:#151433}}.planet-line{{padding:5mm 6mm;border-bottom:1px solid #292640}}.planet-line:last-child{{border:0}}.planet-line h3{{margin:0 0 1mm;color:#bdb7c0;font-size:16px}}.planet-line b{{display:block;color:#d3a840}}.planet-line span{{display:block;color:#6d697d}}.planet-line p{{margin:1mm 0 0}}.story-card{{padding:7mm}}.story-card p{{margin:0 0 4mm}}blockquote{{margin:6mm 0 0;padding-left:5mm;border-left:1px solid #d3a840;color:#aaa3b0;font-size:15px;font-style:italic}}.factor{{margin-top:5mm;padding:6mm}}.factor>div{{display:flex;justify-content:space-between}}.factor small,.factor footer,.number-list small{{color:#5f5b70;font-size:9px;letter-spacing:1px}}.factor h3{{margin:4mm 0 2mm;color:#c6c0c4;font-size:16px}}.factor p{{margin:0}}.factor footer{{margin-top:5mm;padding-top:3mm;border-top:1px solid #272540}}.scale-card{{margin-top:5mm;padding:6mm}}.scale-row{{margin-top:4mm}}.scale-row>div{{display:flex;justify-content:space-between}}.scale-row i{{display:block;height:1.5mm;margin-top:1mm;background:#252341;border-radius:2mm;overflow:hidden}}.scale-row em{{display:block;height:100%;background:#d3a840}}.resource-grid{{display:grid;gap:4mm}}.resource-grid article{{position:relative;padding:6mm}}.resource-grid small{{position:absolute;right:6mm;color:#514e65}}.resource-grid p{{margin:3mm 0 0}}.number-list{{overflow:hidden}}.number-list article{{display:grid;grid-template-columns:10mm 1fr;gap:2mm;padding:6mm;border-bottom:1px solid #292640}}.number-list article:last-child{{border:0}}.number-list>article>b{{color:#d3a840;font:18px Georgia,serif}}.number-list h3{{margin:0 0 2mm;color:#c7c1c5;font-size:16px}}.number-list p{{margin:0}}.number-list small{{display:block;margin-top:2mm}}.final>article{{padding:8mm}}.final h2 em{{color:#d3a840}}.final>article>p{{margin:0 0 5mm}}.final footer{{display:flex;align-items:center;gap:4mm;margin-top:8mm;color:#d3a840;font-size:9px;letter-spacing:1.8px}}@media print{{.section-head{{break-after:avoid}}.key-grid,.wheel-notes,.factor,.scale-card,.planet-line,.resource-grid article,.number-list article,.final>article{{break-inside:avoid}}}}
    </style></head><body>{body}</body></html>'''
