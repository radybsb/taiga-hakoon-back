from taiga.projects.wiki.outline import build_outline


def test_outline_ignores_code_and_reads_markdown_and_html():
    result = build_outline('# Chapter **one**\n\n### Child\n\n```\n# Not a chapter\n```\n\n<h1>HTML &amp; text</h1>')
    assert [(h['level'], h['title']) for h in result] == [(1, 'Chapter one'), (2, 'Child'), (1, 'HTML & text')]


def test_outline_preserves_links_when_renamed_or_inserted():
    before = build_outline('# First\n\n### Child\n\n# Last')
    renamed = build_outline('# Renamed\n\n### Child\n\n# Last', before)
    assert renamed[0]['id'] == before[0]['id']
    inserted = build_outline('# New\n\n# Renamed\n\n### Child\n\n# Last', renamed)
    assert [h['id'] for h in inserted[1:]] == [h['id'] for h in renamed]
    assert inserted[0]['id'] not in [h['id'] for h in renamed]


def test_duplicate_titles_have_unique_ids_and_removal_does_not_reuse_ids():
    before = build_outline('# Same\n\n# Same')
    assert before[0]['id'] != before[1]['id']
    assert build_outline('') == []
    assert build_outline('# New', [])[0]['id'] not in [h['id'] for h in before]


def test_native_editor_headings_and_reordering_keep_identity():
    before = build_outline('## Chapter\n\n### Subchapter\n\n## Other')
    assert [h['level'] for h in before] == [1, 2, 1]
    moved = build_outline('## Other\n\n## Chapter\n\n### Subchapter', before)
    assert [h['id'] for h in moved] == [before[2]['id'], before[0]['id'], before[1]['id']]


def test_setext_heading_from_visual_editor():
    result = build_outline('Chapter\n-------\n\n### Child')
    assert [(h['level'], h['title']) for h in result] == [(1, 'Chapter'), (2, 'Child')]
