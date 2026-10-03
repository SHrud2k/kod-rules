#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate the changelog and before/after cards from edits to data/rules.json.

Compares the working copy of data/rules.json against a git ref (HEAD by
default), detects changed / added / removed / renumbered rules, and then:

  1. stamps "updated": <today> on changed and added rules (drives the
     ОБНОВЛЕНО / NEW badges on the site);
  2. regenerates today's auto entry in data/changelog.json;
  3. regenerates today's "Обновление DD.MM.YYYY" card block in changes.html
     (inserted at the <!-- AUTO-UPDATES --> marker).

Usage:
  python tools/make_changelog.py              # diff vs HEAD
  python tools/make_changelog.py --ref <ref>  # diff vs any commit
  python tools/make_changelog.py --dry-run    # report only, write nothing

Workflow: edit data/rules.json -> run this -> polish the wording in
data/changelog.json and changes.html by hand -> preview -> commit.
Re-running on the same day REGENERATES today's auto entry and card block,
so polish the texts only after the final run.
"""
import argparse
import collections
import datetime
import io
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES = os.path.join(ROOT, 'data', 'rules.json')
CHANGELOG = os.path.join(ROOT, 'data', 'changelog.json')
CHANGES = os.path.join(ROOT, 'changes.html')
MARKER = '<!-- AUTO-UPDATES -->'

CHAPTERS = {'1.1', '1.2', '1.3', '1.4', '1.5', '1.6', '1.7', '1.8', '1.9',
            '2.1', '2.2', '2.3', '2.4', '3.1', '4.1', '4.2', '4.3', '4.4', '4.5',
            '5.1', '5.2', '6.1', '6.2', '7.1', '7.2'}


def load_current():
    return json.load(io.open(RULES, encoding='utf-8'))


def load_at_ref(ref):
    out = subprocess.run(['git', 'show', '%s:data/rules.json' % ref],
                         cwd=ROOT, capture_output=True)
    if out.returncode != 0:
        sys.exit('git show %s:data/rules.json failed: %s' % (ref, out.stderr.decode('utf-8', 'replace')))
    return json.loads(out.stdout.decode('utf-8'))


def flatten(rules):
    """num -> {'html', 'section'} for numbered rules only."""
    flat = {}
    for sec in rules['sections']:
        for c in sec['content']:
            if c.get('num'):
                flat[c['num']] = {'html': c['html'], 'section': sec['id']}
    return flat


def strip_text(html_str, num=None):
    """Readable plain text of a rule for cards and comparison."""
    t = html_str
    if num:
        t = t.replace('<b class="num">%s</b>' % num, '')
    t = re.sub(r'<a class="rref"[^>]*>(.*?)</a>', r'\1', t)
    t = re.sub(r'</p>\s*<p[^>]*>', '\n\n', t)
    t = re.sub(r'<li[^>]*>', '\n— ', t)
    t = re.sub(r'<tr[^>]*>', '\n', t)
    t = re.sub(r'</t[dh]>\s*<t[dh][^>]*>', ' | ', t)
    t = re.sub(r'<[^>]+>', '', t)
    t = t.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    t = re.sub(r'[ \t]+', ' ', t)
    t = re.sub(r'\n{3,}', '\n\n', t)
    return t.strip()


def norm(html_str, num=None):
    return re.sub(r'\s+', ' ', strip_text(html_str, num)).strip()


def diff(old_flat, new_flat):
    changed, removed, added = [], [], []
    for num, o in old_flat.items():
        if num in new_flat:
            if norm(o['html'], num) != norm(new_flat[num]['html'], num):
                changed.append(num)
        else:
            removed.append(num)
    for num in new_flat:
        if num not in old_flat:
            added.append(num)
    # pure renumbering: identical text under a different number
    renumbered = []
    for r in list(removed):
        for a in list(added):
            if norm(old_flat[r]['html'], r) == norm(new_flat[a]['html'], a):
                renumbered.append((r, a))
                removed.remove(r)
                added.remove(a)
                break
    return changed, removed, added, renumbered


def anchor(num):
    return '#r' + num.replace('.', '-')


def validate(rules):
    nums = [c['num'] for s in rules['sections'] for c in s['content'] if c.get('num')]
    dup = [n for n, k in collections.Counter(nums).items() if k > 1]
    tok = re.compile(r'(?<![\d.])(\d+(?:\.\d+)+)(?!\.?\d)')
    broken = sorted({t for s in rules['sections'] for c in s['content']
                     for t in tok.findall(c.get('html', '') + c.get('text', ''))
                     if t not in set(nums) and t not in CHAPTERS})
    return dup, broken


def card(tag, tagcls, head, before, after):
    return ('<div class="item">\n'
            '  <div class="item-head"><span class="tag %s">%s</span><b>%s</b></div>\n'
            '  <div class="diff">\n'
            '    <div class="before"><span class="cap">БЫЛО</span>%s</div>\n'
            '    <div class="after"><span class="cap">СТАЛО</span>%s</div>\n'
            '  </div>\n</div>' % (tagcls, tag, head, before, after))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--ref', default='HEAD', help='git ref to diff against (default HEAD)')
    ap.add_argument('--dry-run', action='store_true', help='report only, write nothing')
    args = ap.parse_args()

    today = datetime.date.today()
    today_iso = today.strftime('%Y-%m-%d')
    today_ru = today.strftime('%d.%m.%Y')

    rules = load_current()
    old_flat = flatten(load_at_ref(args.ref))
    new_flat = flatten(rules)
    changed, removed, added, renumbered = diff(old_flat, new_flat)

    dup, broken = validate(rules)
    if dup:
        sys.exit('ABORT: duplicate rule numbers: %s' % dup)
    if broken:
        print('WARNING: references to non-existent rules: %s' % broken)

    print('vs %s:  changed %d | added %d | removed %d | renumbered %d'
          % (args.ref, len(changed), len(added), len(removed), len(renumbered)))
    for n in changed:
        print('  ~ %s' % n)
    for n in added:
        print('  + %s' % n)
    for n in removed:
        print('  - %s' % n)
    for o, n in renumbered:
        print('  %s -> %s' % (o, n))

    if not (changed or removed or added or renumbered):
        print('No rule changes detected — nothing to do.')
        return
    if args.dry_run:
        print('(dry run — nothing written)')
        return

    # 1) stamp updated dates
    for sec in rules['sections']:
        for c in sec['content']:
            if c.get('num') in changed or c.get('num') in added:
                c['updated'] = today_iso
    io.open(RULES, 'w', encoding='utf-8').write(json.dumps(rules, ensure_ascii=False, indent=2))

    # 2) changelog entry (regenerate today's auto entry)
    items = []
    for n in sorted(changed, key=lambda x: [int(p) for p in x.split('.')]):
        items.append('<a href="%s">%s</a> — правило изменено. ОПИСАТЬ СУТЬ.' % (anchor(n), n))
    for n in sorted(added, key=lambda x: [int(p) for p in x.split('.')]):
        items.append('<a href="%s">%s</a> — новое правило. ОПИСАТЬ СУТЬ.' % (anchor(n), n))
    if removed:
        items.append('Удалены правила: %s.' % ', '.join(sorted(removed)))
    if renumbered:
        items.append('Перенумерация: %s.' % ', '.join('%s → %s' % p for p in renumbered))

    log = json.load(io.open(CHANGELOG, encoding='utf-8'))
    entry = {'date': today_ru, 'auto': True, 'items': items}
    if log['entries'] and log['entries'][0].get('date') == today_ru and log['entries'][0].get('auto'):
        log['entries'][0] = entry
    else:
        log['entries'].insert(0, entry)
    io.open(CHANGELOG, 'w', encoding='utf-8').write(json.dumps(log, ensure_ascii=False, indent=2))

    # 3) changes.html card block (regenerate today's auto block)
    cards = []
    for n in changed:
        cards.append(card('ИЗМЕНЕНО', 'chg', n,
                          strip_text(old_flat[n]['html'], n),
                          strip_text(new_flat[n]['html'], n)))
    for n in added:
        cards.append(card('ДОБАВЛЕНО', 'add', n,
                          '<span class="gone">— правила не было —</span>',
                          strip_text(new_flat[n]['html'], n)))
    for n in removed:
        cards.append(card('УДАЛЕНО', 'del', n,
                          strip_text(old_flat[n]['html'], n),
                          '<span class="gone">— правило удалено —</span>'))
    start = '<!-- AUTO %s START -->' % today_ru
    end = '<!-- AUTO %s END -->' % today_ru
    block = ('%s\n<h2>Обновление %s</h2>\n\n%s\n%s' % (start, today_ru, '\n\n'.join(cards), end))

    ch = io.open(CHANGES, encoding='utf-8').read()
    if start in ch and end in ch:
        ch = re.sub(re.escape(start) + '.*?' + re.escape(end), block, ch, count=1, flags=re.S)
    else:
        if MARKER not in ch:
            sys.exit('ABORT: %s marker not found in changes.html' % MARKER)
        ch = ch.replace(MARKER, MARKER + '\n\n' + block, 1)
    io.open(CHANGES, 'w', encoding='utf-8').write(ch)

    print('\nWritten:')
    print('  data/rules.json      — updated stamps (%s)' % today_iso)
    print('  data/changelog.json  — auto entry for %s (polish the ОПИСАТЬ СУТЬ lines!)' % today_ru)
    print('  changes.html         — card block for %s' % today_ru)
    print('Preview locally, polish wording, then commit.')


if __name__ == '__main__':
    main()
