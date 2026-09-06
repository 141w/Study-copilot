"""persona_discussion 多智能体讨论模式单元测试。

覆盖：
1. 预置角色库 get_persona_presets / resolve_persona 解析
2. discuss 流式生成与多轮轮流发言 (persona_speak)
3. 主持人总结阶段 (summary) 与完成事件 (done)
4. LLM 异常重试与优雅降级 (error)
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.core.persona_discussion import (
    DEFAULT_PERSONAS,
    PERSONA_PRESETS,
    discuss,
    get_persona_presets,
    resolve_persona,
)


def test_persona_presets_catalog():
    presets = get_persona_presets()
    assert len(presets) >= 4
    roles = {p["role"] for p in presets}
    assert {"teacher", "thinker", "curious", "notetaker"}.issubset(roles)
    for p in presets:
        assert p["name"]
        assert p["avatar"]
        assert p["system_message"]


def test_resolve_persona_by_role_or_id():
    resolved = resolve_persona({"role": "teacher"})
    assert resolved["name"] == "苏老师"
    assert resolved["avatar"] == "User"
    assert "主讲老师" in resolved["system_message"]

    custom = resolve_persona({"name": "自定义嘉宾", "system_message": "你是嘉宾"})
    assert custom["name"] == "自定义嘉宾"
    assert custom["system_message"] == "你是嘉宾"


@pytest.mark.asyncio
async def test_discuss_stream_lifecycle():
    """测试多角色讨论全生命周期流式事件。"""
    mock_responses = [
        "从基向量展开看，这非常直观。",      # turn 1: 学霸
        "可是如果维数无限该怎么理解呢？",    # turn 1: 求知同学
        "这是本次讨论的核心要点总结：...",     # 主持人总结
    ]

    with patch("app.core.persona_discussion.LLM") as mock_llm_cls:
        mock_llm = mock_llm_cls.return_value
        mock_llm.chat = AsyncMock(side_effect=mock_responses)

        events = []
        async for ev in discuss(
            topic="什么是希尔伯特空间？",
            personas=[
                {"role": "thinker"},
                {"role": "curious"},
            ],
            context="参考定义：完备的内积空间",
            llm_config={"api_key": "fake", "model": "test-model"},
            max_turns=1,
        ):
            events.append(ev)

        types = [e["type"] for e in events]
        assert "persona_start" in types
        assert "persona_chunk" in types
        assert "persona_speak" in types
        assert "summary_start" in types
        assert "summary_chunk" in types
        assert "summary" in types
        assert types[-1] == "done"

        speaks = [e for e in events if e["type"] == "persona_speak"]
        assert len(speaks) == 2
        assert speaks[0]["persona"] == "学霸"
        assert speaks[0]["content"] == "从基向量展开看，这非常直观。"
        assert speaks[1]["persona"] == "求知同学"
        assert speaks[1]["content"] == "可是如果维数无限该怎么理解呢？"

        summary_event = next(e for e in events if e["type"] == "summary")
        assert summary_event["persona"] == "主持人"
        assert summary_event["content"] == "这是本次讨论的核心要点总结：..."

        done_event = events[-1]
        assert done_event["total_turns"] == 2


def test_build_peer_context_section():
    """测试 OpenMAIC peer-context 算法提取与互辩提示生成。"""
    from app.core.persona_discussion import build_peer_context_section

    # 空历史返回空字符串
    assert build_peer_context_section([], "求知同学") == ""

    history = [
        {"role": "assistant", "content": "【学霸】：装饰器本质是闭包和高阶函数语法糖。"},
    ]
    ctx = build_peer_context_section(history, "求知同学")
    assert "同伴发言观点" in ctx
    assert "装饰器本质是闭包和高阶函数语法糖" in ctx
    assert "研讨互辩要求（你当前是 求知同学）" in ctx
    assert "严禁自说自话" in ctx

    # 过滤自身发言
    self_history = [
        {"role": "assistant", "content": "【求知同学】：我有个问题。"},
    ]
    assert build_peer_context_section(self_history, "求知同学") == ""


@pytest.mark.asyncio
async def test_discuss_error_graceful_handling():
    """测试 LLM 失败时产出 error 事件且流正常 done，不向外抛未捕获异常。"""
    with patch("app.core.persona_discussion.LLM") as mock_llm_cls:
        mock_llm = mock_llm_cls.return_value
        mock_llm.chat = AsyncMock(side_effect=RuntimeError("API quota exceeded"))

        events = []
        async for ev in discuss(
            topic="测试失败",
            personas=DEFAULT_PERSONAS,
            llm_config={"api_key": "fake"},
            max_turns=1,
        ):
            events.append(ev)

        types = [e["type"] for e in events]
        assert "error" in types
        assert types[-1] == "done"


@pytest.mark.asyncio
async def test_discuss_token_chunk_streaming():
    """测试多角色讨论逐 token 流式输出。"""
    async def mock_stream(messages, temperature=0.7):
        for token in ["代", "码", "示", "例"]:
            yield token

    with patch("app.core.persona_discussion.LLM") as mock_llm_cls:
        mock_llm = mock_llm_cls.return_value
        mock_llm.chat_stream = mock_stream

        chunks = []
        events = []
        async for ev in discuss(
            topic="装饰器",
            personas=[{"role": "thinker"}],
            max_turns=1,
        ):
            events.append(ev)
            if ev["type"] == "persona_chunk":
                chunks.append(ev["delta"])

        assert chunks == ["代", "码", "示", "例"]
        speak_ev = next(e for e in events if e["type"] == "persona_speak")
        assert speak_ev["content"] == "代码示例"


@pytest.mark.asyncio
async def test_discuss_multi_turn_clean_messages():
    """测试多轮讨论中消息结构规范，绝不包含连续 assistant 角色，杜绝大模型 API 早停。"""
    captured_messages = []

    async def capture_stream(messages, temperature=0.8):
        captured_messages.append(messages)
        yield "论点输出"

    with patch("app.core.persona_discussion.LLM") as mock_llm_cls:
        mock_llm = mock_llm_cls.return_value
        mock_llm.chat_stream = capture_stream

        events = []
        async for ev in discuss(
            topic="生成器与迭代器",
            personas=[{"role": "thinker"}, {"role": "curious"}],
            max_turns=2,
        ):
            events.append(ev)

        # 2 轮 × 2 角色 + 1 次主持人总结 = 5 次调用
        assert len(captured_messages) == 5
        for call_idx, msgs in enumerate(captured_messages):
            # 每一次调用严格为 [system, user]，绝不出现连续 assistant 消息堆叠
            roles = [m["role"] for m in msgs]
            assert roles == ["system", "user"], f"Call {call_idx} had unexpected roles: {roles}"

        # 验证第二轮中的 user prompt 包含第一轮研讨纪要
        round2_prompt = captured_messages[2][1]["content"]
        assert "第 1 轮研讨发言" in round2_prompt
        assert "学霸" in round2_prompt


@pytest.mark.asyncio
async def test_discuss_empty_stream_recovery():
    """测试当流式偶发返回空 token 时，自动降级并自愈，绝不向前端推送空内容。"""
    call_count = 0

    async def empty_stream(messages, temperature=0.8):
        # 模拟模型第一轮流式空输出
        nonlocal call_count
        call_count += 1
        if False:
            yield ""

    with patch("app.core.persona_discussion.LLM") as mock_llm_cls:
        mock_llm = mock_llm_cls.return_value
        mock_llm.chat_stream = empty_stream
        # 降级回退的 chat 成功返回内容
        mock_llm.chat = AsyncMock(return_value="降级自愈成功论点")

        events = []
        async for ev in discuss(
            topic="闭包原理",
            personas=[{"role": "thinker"}],
            max_turns=1,
        ):
            events.append(ev)

        speak_ev = next(e for e in events if e["type"] == "persona_speak")
        assert speak_ev["content"] == "降级自愈成功论点"
        assert speak_ev["content"] != ""

