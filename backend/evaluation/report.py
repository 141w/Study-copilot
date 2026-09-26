"""报表生成：每方法 JSON + 汇总 Markdown（含运行参数与历史对比）。"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

from evaluation.harness import Metrics

_TS_RE = re.compile(r"-(\d{8}T\d{6}Z)\.json$")


def write_report(
    results: list[Metrics],
    meta: dict[str, object],
    out_dir: str | Path,
) -> tuple[Path, Path]:
    """落盘报表，返回 (summary_md_path, latest_json_path)。"""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

    # 1. 每方法 JSON（含完整 meta，保证可复现追溯）
    for m in results:
        (out / f"{m.name}-{ts}.json").write_text(
            json.dumps({"meta": meta, "metrics": m.to_dict()}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # 2. 汇总 Markdown
    ks = sorted(results[0].recall) if results else []
    corpus_mode = str(meta.get("corpus") or "sampled")
    tag = str(meta.get("tag") or "")
    lines = [
        "# 检索召回率评测报表",
        "",
        f"- 时间（UTC）: {ts}",
        f"- 数据集: {meta.get('datasets')}",
        f"- 方法: {meta.get('methods')}",
        f"- n_queries={meta.get('n_queries')}, seed={meta.get('seed')}, "
        f"distractor_ratio={meta.get('distractor_ratio')}, top_k={meta.get('top_k')}",
        f"- corpus={corpus_mode}, tag={tag or '-'}",
        f"- embedding: {meta.get('embedding_model')}",
        "",
        "| 数据集×方法 | queries | "
        + " | ".join(f"R@{k}" for k in ks)
        + " | MRR@10 | nDCG@10 | CP@10 |",
        "|" + "---|" * (5 + len(ks)),
    ]
    for m in results:
        cells = [m.name, str(m.n_queries)] + [f"{m.recall[k]:.4f}" for k in ks]
        cells += [
            f"{m.mrr.get(10, 0.0):.4f}",
            f"{m.ndcg.get(10, 0.0):.4f}",
            f"{m.ctx_precision.get(10, 0.0):.4f}",
        ]
        lines.append("| " + " | ".join(cells) + " |")

    # 3. 历史对比（同 dataset×method 的 Recall@10 环比）
    history = _load_history(out, ts)
    if history:
        lines += [
            "",
            "## 历史对比（Recall@10 环比）",
            "",
            "| 数据集×方法 | 上次 | 本次 | Δ |",
            "|---|---|---|---|",
        ]
        for m in results:
            prev = history.get(m.name)
            if prev is None:
                continue
            cur = m.recall.get(10, 0.0)
            lines.append(f"| {m.name} | {prev:.4f} | {cur:.4f} | {cur - prev:+.4f} |")

    lines += [
        "",
        "## 环境说明",
        "",
    ]
    if tag == "zh":
        lines.append(
            "- hybrid 评测实例已启用 zhparser（FTS 配置 zh），中文全文通道生效；"
            "结果与 simple 降级口径不可直接混比（按 meta.tag 区分）。"
        )
    else:
        lines.append(
            "- hybrid 评测实例未安装 zhparser：PostgreSQL 全文配置降级为 simple，"
            "中文词法通道近乎失效，hybrid 分数为向量主导的 RRF；生产（zhparser 就绪）会更高。"
        )
    if corpus_mode == "full":
        lines.append(
            "- corpus=full：候选池为完整数据集 corpus（对齐 MTEB/BEIR 全库排名口径），"
            "distractor_ratio 不适用；绝对分数与 sampled 口径不可直接比较。"
        )
    lines += [
        "- reranker 为 cross-encoder/ms-marco-MiniLM-L-6-v2（英文训练）；"
        "中文数据集上 rerank 增益可能有限，英文 FinanceQA 上应显著。",
        "- 指标口径：Recall@k=|top-k∩relevant|/|relevant|；MRR/nDCG 为排序质量；"
        "CP@10 为 top-10 平均精度（qrels 二值判据，与 RAGAS context_precision 同构）；"
        "无相关标注的 query 不参与统计。",
        "",
    ]
    summary_path = out / f"summary-{ts}.md"
    summary_path.write_text("\n".join(lines), encoding="utf-8")
    return summary_path, summary_path


def _load_history(out: Path, current_ts: str) -> dict[str, float]:
    """读取本目录下除本次外的历史 JSON，返回 name -> 最近一次 Recall@10。"""
    latest: dict[str, tuple[str, float]] = {}
    for path in out.glob("*-2*.json"):
        if current_ts in path.name:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 - 历史文件损坏不影响本次报表
            continue
        if not isinstance(data, dict):
            continue  # 专项评测 JSON（chunking/agentic 等顶层为 list）非方法级结果
        metrics = data.get("metrics", {})
        name = metrics.get("name")
        recall10 = (metrics.get("recall") or {}).get("10")
        if not name or recall10 is None:
            continue
        # 时间戳从文件名尾部正则提取——rsplit 在带口径后缀的文件名
        # （如 cmedqa-bm25-full-zh-<ts>.json）下会取错字段
        ts_match = _TS_RE.search(path.name)
        if not ts_match:
            continue
        stamp = ts_match.group(1)
        if name not in latest or stamp > latest[name][0]:
            latest[name] = (stamp, float(recall10))
    return {name: val for name, (_, val) in latest.items()}
