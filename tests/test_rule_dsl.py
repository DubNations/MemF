from cognitive_os.rules.dsl_evaluator import evaluate_condition


def test_safe_dsl_accepts_valid_expression():
    env = {"goal": "x", "boundary": "global", "knowledge_count": 10, "metadata": {"scenario": "learning_exam_prep"}}
    result = evaluate_condition("knowledge_count >= 5 and metadata['scenario'] == 'learning_exam_prep'", env)
    assert result.ok is True
    assert result.value is True


def test_safe_dsl_blocks_calls():
    env = {"goal": "x", "boundary": "global", "knowledge_count": 10, "metadata": {}}
    result = evaluate_condition("__import__('os').system('echo hi')", env)
    assert result.ok is False
    assert result.value is False
