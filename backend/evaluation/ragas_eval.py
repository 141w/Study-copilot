"""P6 RAGAS 端到端评测（在隔离 ragas venv 中运行）：

    /path/ragas-venv/bin/python evaluation/ragas_eval.py \
        --input evaluation/data/ragas_data.json --out evaluation/data/ragas_result.json

指标（LLM-as-judge）：
- context_recall: ground_truth 所需信息是否被召回的 context 覆盖（与检索召回强相关）
- faithfulness:   答案是否忠于 context（无幻觉）
- noise_precision / noise_sensitivity: 噪声鲁棒性（需 ragas_prep --noise 数据，默认不启用）

通过 --metrics 选择指标（逗号分隔，默认 context_recall,faithfulness）。
不含 answer_relevancy：其依赖 embeddings（默认 OpenAI），与自定义 base_url 不兼容。

judge 配置优先级（异构 judge 是端到端结论可信度的关键——尽量与生成模型不同源）：
1. 环境变量 RAGAS_JUDGE_API_KEY / RAGAS_JUDGE_BASE_URL / RAGAS_JUDGE_MODEL
2. backend/.env 的 OPENAI_API_KEY / OPENAI_BASE_URL / OPENAI_MODEL（旧行为，向后兼容）
"""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path


def _load_dotenv() -> dict[str, str]:
    """极简 .env 解析（KEY=VALUE，去引号，跳过注释）。"""
    env: dict[str, str] = {}
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return env
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip().strip("\"'")
    return env


# 指标名 -> ragas.metrics 模块属性；noise 系需 prep 侧 --noise 数据
_METRIC_ATTRS = {
    "context_recall": "context_recall",
    "faithfulness": "faithfulness",
    "noise_precision": "noise_precision",
    "noise_sensitivity": "noise_sensitivity",
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="evaluation.ragas_eval", description="RAGAS 端到端评测（ragas venv 运行）"
    )
    parser.add_argument("--input", default="evaluation/data/ragas_data.json")
    parser.add_argument("--out", default="evaluation/data/ragas_result.json")
    parser.add_argument(
        "--metrics",
        default="context_recall,faithfulness",
        help=f"逗号分隔指标（可选：{','.join(_METRIC_ATTRS)}）",
    )
    args = parser.parse_args(argv)

    metric_names = [m.strip() for m in args.metrics.split(",") if m.strip()]
    unknown = [m for m in metric_names if m not in _METRIC_ATTRS]
    if unknown:
        print(f"[ragas] 未知指标: {unknown}; 可选: {list(_METRIC_ATTRS)}")
        return 2

    env = _load_dotenv()
    api_key = os.environ.get("RAGAS_JUDGE_API_KEY") or env.get("OPENAI_API_KEY", "")
    base_url = os.environ.get("RAGAS_JUDGE_BASE_URL") or env.get(
        "OPENAI_BASE_URL", "https://api.openai.com/v1"
    )
    model = os.environ.get("RAGAS_JUDGE_MODEL") or env.get("OPENAI_MODEL", "gpt-3.5-turbo")
    judge_source = (
        "env(RAGAS_JUDGE_*)" if os.environ.get("RAGAS_JUDGE_MODEL") else "dotenv(OPENAI_*)"
    )
    if not api_key:
        print("[ragas] 缺少 judge API key（RAGAS_JUDGE_API_KEY 或 .env OPENAI_API_KEY）")
        return 2

    import ragas.metrics
    from langchain_openai import ChatOpenAI
    from ragas import EvaluationDataset, evaluate
    from ragas.llms import LangchainLLMWrapper

    metrics = []
    for name in metric_names:
        attr = getattr(ragas.metrics, _METRIC_ATTRS[name], None)
        if attr is None:
            print(f"[ragas] 当前 ragas 版本不提供指标 {_METRIC_ATTRS[name]}，请升级或去掉该指标")
            return 2
        metrics.append(attr)

    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    if not data:
        print("[ragas] 输入为空")
        return 2

    dataset = EvaluationDataset.from_list(
        [
            {
                "user_input": d["question"],
                "retrieved_contexts": d["contexts"],
                "response": d["answer"],
                "reference": d["ground_truth"],
            }
            for d in data
        ]
    )

    judge = LangchainLLMWrapper(
        ChatOpenAI(model=model, base_url=base_url, api_key=api_key, temperature=0)
    )
    print(f"[ragas] judge={model} @ {base_url}（配置来源: {judge_source}），样本 {len(data)} 条")

    result = evaluate(
        dataset,
        metrics=metrics,
        llm=judge,
        raise_exceptions=False,
    )
    df = result.to_pandas()

    # 按数据集分组汇总（df 行序与输入一致；NaN = judge 调用失败，跳过不计）
    per_dataset: dict[str, dict[str, object]] = {}
    for d, row in zip(data, df.itertuples()):
        bucket = per_dataset.setdefault(d["dataset"], {"n": 0})
        bucket["n"] = bucket["n"] + 1
        for metric in metric_names:
            val = getattr(row, metric, None)
            if val is None:
                continue
            val = float(val)
            if math.isnan(val):
                continue
            b = bucket.setdefault(metric, {"sum": 0.0, "n": 0})
            b["sum"] += val
            b["n"] += 1

    def _agg(bucket: dict, metric: str) -> float | None:
        b = bucket.get(metric)
        return round(b["sum"] / b["n"], 4) if b and b["n"] else None

    summary = {
        "judge": {"model": model, "base_url": base_url, "source": judge_source},
        "metrics": metric_names,
        "n_samples": len(data),
        **{
            f"n_valid_{metric}": int(df[metric].notna().sum())
            for metric in metric_names
            if metric in df.columns
        },
        "overall": {
            metric: (round(df[metric].mean(), 4) if metric in df.columns else None)
            for metric in metric_names
        },
        "per_dataset": {
            name: {
                "n": bucket["n"],
                **{metric: _agg(bucket, metric) for metric in metric_names},
            }
            for name, bucket in per_dataset.items()
        },
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"[ragas] 结果 -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
