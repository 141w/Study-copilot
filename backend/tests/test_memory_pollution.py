
"""记忆召回的跨主题污染防护测试。

事故背景：用户同时有「加涅学习理论」记忆与「分布式系统」文档时，
问「超时机制」会被召回加涅 task/interest 注入 system prompt，导致跑题。
根因：CJK 逐字分词 + 高频虚字（及/有/的/中）造成虚假词法匹配。
"""
import pytest


class TestLexicalScoreStopChars:
    """compute_lexical_score 的高频虚字剔除"""

    def test_high_freq_chars_do_not_match(self):
        """「及/有/的」等虚字重叠不计分"""
        from app.services.memory_service import compute_lexical_score
        # 查询含「及」，item 含「及」「有」——仅虚字重叠，score 应为 0
        score = compute_lexical_score(
            query_tokens={"总", "结", "及"},
            query_bigrams=set(),
            item_tokens={"掌", "握", "及", "有"},
            item_bigrams=set(),
        )
        assert score == 0.0

    def test_bigram_match_still_counts(self):
        """实义 bigram 匹配保持 3 倍权重（bigram 不受虚字表影响）"""
        from app.services.memory_service import compute_lexical_score
        score = compute_lexical_score(
            query_tokens={"超", "时"},
            query_bigrams={"超时"},
            item_tokens={"超", "时"},
            item_bigrams={"超时"},
        )
        # bigram 3 + 单字「超」1 分（「时」属高频虚字表，单字不计，bigram 已覆盖）
        assert score == 4.0

    def test_real_token_overlap_counts(self):
        """实义单字重叠计 1 分"""
        from app.services.memory_service import compute_lexical_score
        score = compute_lexical_score(
            query_tokens={"教", "育"},
            query_bigrams=set(),
            item_tokens={"教", "育", "学"},
            item_bigrams=set(),
        )
        assert score == 2.0

    def test_english_tokens_untouched(self):
        """英文 token 不受虚字表影响"""
        from app.services.memory_service import compute_lexical_score
        score = compute_lexical_score(
            query_tokens={"raft"},
            query_bigrams=set(),
            item_tokens={"raft"},
            item_bigrams=set(),
        )
        assert score == 1.0


class TestRecallNoCrossTopicPollution:
    """recall 的跨主题污染防护（真实数据库，活跃用户）"""

    @pytest.fixture
    async def _setup(self):
        # 依赖 conftest 的 db fixture；无则跳过
        yield

    async def test_offtopic_query_excludes_interest(self):
        """与查询无关的 interest（加涅）不注入信封"""
        from sqlalchemy import select

        from app.db import AsyncSessionLocal, MemoryItem, User
        from app.services.memory_service import memory_service

        async with AsyncSessionLocal() as db:
            user = (await db.execute(select(User).limit(1))).scalar_one()
            # 确认用户有加涅相关记忆（测试前置）
            items = (
                await db.execute(
                    select(MemoryItem).where(
                        MemoryItem.user_id == user.id,
                        MemoryItem.status == "active",
                        MemoryItem.content.like("%加涅%"),
                    )
                )
            ).scalars().all()
            if not items:
                pytest.skip("用户无加涅记忆，跳过")
            r = await memory_service.recall(
                user.id, "总结文档中所有涉及超时的机制及其超时语义", db
            )
            env = r.prompt_envelope or ""
            # 断言：信封中不出现加涅 task/interest（常驻 profile 不含「加涅」字样即可）
            assert "加涅" not in env, f"跨主题污染: {env[:200]}"

    async def test_ontopic_query_keeps_interest(self):
        """相关查询（加涅）仍注入加涅记忆"""
        from sqlalchemy import select

        from app.db import AsyncSessionLocal, MemoryItem, User
        from app.services.memory_service import memory_service

        async with AsyncSessionLocal() as db:
            user = (await db.execute(select(User).limit(1))).scalar_one()
            items = (
                await db.execute(
                    select(MemoryItem).where(
                        MemoryItem.user_id == user.id,
                        MemoryItem.status == "active",
                        MemoryItem.content.like("%加涅%"),
                    )
                )
            ).scalars().all()
            if not items:
                pytest.skip("用户无加涅记忆，跳过")
            r = await memory_service.recall(
                user.id, "加涅学习层次八类分法的教学应用", db
            )
            env = r.prompt_envelope or ""
            assert "加涅" in env, "相关查询应保留加涅记忆"
