"""Agent XML 工具调用兼容层的单元测试。

背景：step-3.7-flash 偶发不遵守 OpenAI tool_calls 协议，把工具调用写成
XML 文本混进 content，导致原始 XML 泄漏进最终答案。
"""
import pytest


def _build_content(tool_name, params):
    """构造含 XML 工具调用的 content（避免测试文件出现字面闭合标签）"""
    open_fn = chr(60) + "function=" + tool_name + chr(62)
    close_fn = chr(60) + chr(47) + "function" + chr(62)
    parts = ["思考中...", open_fn]
    for k, v in params.items():
        parts.append(chr(60) + "parameter=" + k + chr(62))
        parts.append(v)
        parts.append(chr(60) + chr(47) + "parameter" + chr(62))
    parts.append(close_fn)
    parts.append("继续输出")
    return "\n".join(parts)


class TestXmlToolCallParser:
    def test_single_call_parsed(self):
        """单工具调用解析为结构化 tool_calls"""
        from app.agent.engine import _parse_xml_tool_calls

        content = _build_content("knowledge_search", {
            "doc_ids": '["doc-123"]',
            "query": "超时机制",
        })
        calls = _parse_xml_tool_calls(content)
        assert len(calls) == 1
        assert calls[0]["function"]["name"] == "knowledge_search"
        import json
        args = json.loads(calls[0]["function"]["arguments"])
        assert args["doc_ids"] == ["doc-123"]
        assert args["query"] == "超时机制"

    def test_multiple_calls_parsed(self):
        """多个工具调用全部解析"""
        from app.agent.engine import _parse_xml_tool_calls

        content = (
            _build_content("knowledge_search", {"query": "问题一"})
            + "\n"
            + _build_content("grep_chunks", {"query": "问题二"})
        )
        calls = _parse_xml_tool_calls(content)
        assert len(calls) == 2
        assert calls[0]["function"]["name"] == "knowledge_search"
        assert calls[1]["function"]["name"] == "grep_chunks"

    def test_non_json_value_kept_as_string(self):
        """非 JSON 参数值按字符串保留"""
        from app.agent.engine import _parse_xml_tool_calls

        content = _build_content("get_document_info", {"doc_ids": "not-a-json"})
        calls = _parse_xml_tool_calls(content)
        import json
        args = json.loads(calls[0]["function"]["arguments"])
        assert args["doc_ids"] == "not-a-json"

    def test_plain_content_no_calls(self):
        """普通文本不产生调用"""
        from app.agent.engine import _parse_xml_tool_calls

        assert _parse_xml_tool_calls("这是一段普通回答，没有任何工具调用。") == []

    def test_call_ids_unique(self):
        """多个调用的 id 唯一"""
        from app.agent.engine import _parse_xml_tool_calls

        content = (
            _build_content("knowledge_search", {"query": "a"})
            + "\n" + _build_content("knowledge_search", {"query": "b"})
        )
        calls = _parse_xml_tool_calls(content)
        assert calls[0]["id"] != calls[1]["id"]
