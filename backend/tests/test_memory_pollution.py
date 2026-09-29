
"""记忆召回的跨主题污染防护测试。

事故背景：用户同时有「加涅学习理论」记忆与「分布式系统」文档时，
问「超时机制」会被召回加涅 task/interest 注入 system prompt，导致跑题。
根因：CJK 逐字分词 + 高频虚字（及/有/的/中）造成虚假词法匹配。
"""


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
    """recall 的跨主题污染防护。

    原先这两个用例直接 `from app.db import AsyncSessionLocal` 取全局会话工厂，
    连的是 DATABASE_URL 指向的库：开发机上是个人真实库（有用户、有「加涅」记忆）
    所以绿，CI 的 ci-test.db 从未 create_all → `no such table: users`。
    也就是说这道防护只在装了个人数据的那台机器上真的跑过。

    改为走 conftest 的 db_session fixture 并自建最小数据，任何环境下都真的断言。
    """

    USER_ID = "memory-pollution-user"

    async def _seed(self, db) -> None:
        """一个用户 + 一条「加涅」interest，复现事故时的记忆构成。"""
        from app.db import MemoryItem, User

        db.add(
            User(
                id=self.USER_ID,
                username="memory_pollution_u",
                email="memory-pollution@example.com",
                password_hash="x" * 60,
            )
        )
        db.add(
            MemoryItem(
                id="mp-interest-gagne",
                user_id=self.USER_ID,
                kind="interest",
                origin="explicit",
                status="active",
                key="interest",
                content="教育心理学：加涅的学习条件与八类学习层次",
            )
        )
        await db.commit()

    async def test_offtopic_query_excludes_interest(self, db_session):
        """与查询无关的 interest（加涅）不注入信封"""
        from app.services.memory_service import memory_service

        await self._seed(db_session)
        r = await memory_service.recall(
            self.USER_ID, "总结文档中所有涉及超时的机制及其超时语义", db_session
        )
        env = r.prompt_envelope or ""
        # 断言：信封中不出现加涅 interest（常驻 profile 不含「加涅」字样即可）
        assert "加涅" not in env, f"跨主题污染: {env[:200]}"

    async def test_ontopic_query_keeps_interest(self, db_session):
        """相关查询（加涅）仍注入加涅记忆——防止防护过头把 interest 全砍掉"""
        from app.services.memory_service import memory_service

        await self._seed(db_session)
        r = await memory_service.recall(
            self.USER_ID, "加涅学习层次八类分法的教学应用", db_session
        )
        env = r.prompt_envelope or ""
        assert "加涅" in env, "相关查询应保留加涅记忆"
