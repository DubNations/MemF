from cognitive_os.rules.rule import Rule
from cognitive_os.rules.simulator import simulate_rules


def test_simulate_rules_matches_and_diagnostics():
    rules = [
        Rule(
            id="r1",
            scope="compliance",
            condition="knowledge_count >= 2",
            action_constraint="must cite",
            priority=10,
            applicable_boundary="global",
        ),
        Rule(
            id="r2",
            scope="freshness",
            condition="bad_syntax(",
            action_constraint="should fail",
            priority=5,
            applicable_boundary="global",
        ),
    ]

    ret = simulate_rules(rules, goal="x", boundary="global", metadata={"scenario": "finance"}, knowledge_count=3)
    assert ret["matched_count"] == 1
    assert ret["matched"][0]["rule_id"] == "r1"
    assert ret["diagnostics"][0]["rule_id"] == "r2"
