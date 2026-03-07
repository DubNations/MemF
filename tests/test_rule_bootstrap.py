from cognitive_os.rules.rule_bootstrap import _clean_html, bootstrap_rules_from_web


def test_clean_html_removes_tags():
    html = "<html><style>.x{}</style><body><h1>must comply</h1><script>x=1</script></body></html>"
    text = _clean_html(html)
    assert "must comply" in text
    assert "script" not in text.lower()


def test_bootstrap_rules_fallback_for_unknown_domain():
    result = bootstrap_rules_from_web(domain="unknown_domain", max_rules=3, timeout_sec=1)
    assert len(result.rules) == 3
    assert all(r.id.startswith("tpl_") for r in result.rules)
