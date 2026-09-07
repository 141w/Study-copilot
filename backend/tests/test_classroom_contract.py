"""Vendored 上游契约锁定测试（OpenMAIC 课堂引擎）。

作用：把主系统对 classroom/ 引擎（Vendored 的 THU-MAIC/OpenMAIC 快照，
基线见 classroom/VENDORED.md）的全部耦合面固化为可执行断言。

- 不依赖网络、不启动引擎、不 mock LLM —— 全部读取仓库内真实文件。
- 平时：随测试套运行，验证定制/重构未意外破坏对引擎的调用前提。
- 升级上游时：先跑本文件，任何断言变红 = 契约漂移，必须先修集成层
  （见 VENDORED.md 第 4 节升级 SOP）。

三个锁定面：
1. HTTP 端点存在性与路由形状（app/api/generate-classroom/）
2. 轮询响应 JSON 字段契约（~12 字段 + status 枚举）
3. DSL 数据 schema 与本仓库本地生成器（build_classroom_dsl）的同构性
"""

import json
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_ROOT.parent
ENGINE_ROOT = PROJECT_ROOT / "classroom"

# ── 耦合面 1：HTTP 端点存在性 ─────────────────────────────────────────────


def test_engine_submit_endpoint_exists():
    """上游必须继续提供 POST /api/generate-classroom（主系统提交生成任务的唯一入口）。"""
    route = ENGINE_ROOT / "app" / "api" / "generate-classroom" / "route.ts"
    assert route.is_file(), f"引擎提交端点路由文件丢失: {route}"
    body = route.read_text(encoding="utf-8")
    assert "export async function POST" in body, "提交端点不再导出 POST 处理器"


def test_engine_poll_endpoint_exists():
    """上游必须继续提供 GET /api/generate-classroom/{jobId}（轮询通道的根）。"""
    route = ENGINE_ROOT / "app" / "api" / "generate-classroom" / "[jobId]" / "route.ts"
    assert route.is_file(), f"引擎状态轮询路由文件丢失: {route}"
    body = route.read_text(encoding="utf-8")
    assert "export async function GET" in body, "轮询端点不再导出 GET 处理器"


# ── 耦合面 2：轮询响应字段契约 ────────────────────────────────────────────

POLL_RESPONSE_FIELDS = [
    "jobId",
    "status",
    "step",
    "progress",
    "message",
    "pollUrl",
    "pollIntervalMs",
    "scenesGenerated",
    "totalScenes",
    "result",
    "error",
    "done",
]


def test_poll_response_field_contract():
    """轮询响应必须包含主系统解析的全部字段（classroom_service.poll_generation_status 依赖）。"""
    route = ENGINE_ROOT / "app" / "api" / "generate-classroom" / "[jobId]" / "route.ts"
    body = route.read_text(encoding="utf-8")
    missing = [f for f in POLL_RESPONSE_FIELDS if f not in body]
    assert not missing, f"引擎轮询响应丢失字段（上游契约漂移）: {missing}"


@pytest.mark.parametrize("field", ["jobId", "status", "result", "pollUrl"])
def test_backend_consumes_fields_exist_in_engine(field: str):
    """主系统读取的关键字段必须在上游响应构造代码中出现（拼写/重命名漂移探测）。

    兼容两种构造形式：`field: value` 与 shorthand `field,`。
    """
    route = ENGINE_ROOT / "app" / "api" / "generate-classroom" / "[jobId]" / "route.ts"
    body = route.read_text(encoding="utf-8")
    assert f"{field}:" in body or f"{field}," in body, (
        f"上游响应构造中不再包含字段 {field}"
    )


def test_job_status_enum_contract():
    """job-store 的状态枚举必须保持类型声明四值：queued/running/succeeded/failed。

    注意：初始态是 queued（非 pending）；主系统判定完成依赖
    status in ('succeeded', 'completed') 与 done 标志（classroom_service.py）。
    """
    store = ENGINE_ROOT / "lib" / "server" / "classroom-job-store.ts"
    assert store.is_file(), f"引擎 job-store 丢失: {store}"
    body = store.read_text(encoding="utf-8")
    assert "export type ClassroomGenerationJobStatus" in body, (
        "job-store 状态类型声明丢失（枚举可能被重命名）"
    )
    for status in ("queued", "running", "succeeded", "failed"):
        assert f"'{status}'" in body, f"job-store 状态枚举丢失 {status}（主系统判定逻辑将失效）"


def test_result_contract_fields():
    """result 载荷必须携带 classroomId（上游 job-store 落值），URL 字段需保留。"""
    store = ENGINE_ROOT / "lib" / "server" / "classroom-job-store.ts"
    body = store.read_text(encoding="utf-8")
    assert "classroomId: string" in body, "result.classroomId 类型声明丢失"


# ── 耦合面 3：DSL schema 同构锁定 ────────────────────────────────────────

DSL_TOP_KEYS = {"id", "url", "stage", "scenes", "scenesCount", "createdAt"}
STAGE_KEYS = {"id", "name", "description", "createdAt", "updatedAt", "style", "languageDirective", "generatedAgentConfigs"}
SCENE_KEYS = {"id", "stageId", "title", "order", "type", "content", "actions", "createdAt", "updatedAt"}


def _load_engine_dsl_sample() -> dict:
    """读取引擎真实产物样本（上游生成的课堂 JSON）。"""
    sample_dir = ENGINE_ROOT / "data" / "classrooms"
    files = sorted(sample_dir.glob("*.json"))
    assert files, "classroom/data/classrooms 无样本可锁定 DSL schema（引擎生成一次后回填样本）"
    return json.loads(files[0].read_text(encoding="utf-8"))


def test_engine_dsl_top_level_schema():
    dsl = _load_engine_dsl_sample()
    missing = DSL_TOP_KEYS - set(dsl.keys())
    assert not missing, f"引擎 DSL 顶层字段漂移: {missing}"
    assert dsl["scenesCount"] == len(dsl["scenes"]), "scenesCount 与 scenes 长度不一致"


def test_engine_dsl_stage_schema():
    dsl = _load_engine_dsl_sample()
    missing = STAGE_KEYS - set(dsl["stage"].keys())
    assert not missing, f"引擎 DSL stage 字段漂移: {missing}"


def test_engine_dsl_scene_schema():
    dsl = _load_engine_dsl_sample()
    for scene in dsl["scenes"]:
        missing = SCENE_KEYS - set(scene.keys())
        assert not missing, f"scene 字段漂移（scene.id={scene.get('id', '?')}）: {missing}"


# ── 本地生成器与引擎 DSL 同构（本地保底路径的隐藏耦合） ──────────────────


def test_local_dsl_isomorphic_with_engine_schema():
    """build_classroom_dsl 产物必须与引擎 DSL schema 同构。

    引擎不可达时本地保底生成的课件由引擎播放器渲染；schema 漂移会导致
    本地路径生成的课堂白屏——平时最难被测试覆盖的路径。
    """
    from app.core.course_generator import build_classroom_dsl

    outline = {
        "title": "契约同构测试微课",
        "description": "锁定本地 DSL 与引擎 schema 同构",
        "sections": [
            {"id": "sec-1", "title": "样例章节", "key_points": ["要点一", "要点二"]},
        ],
    }
    quizzes = [
        {
            "section_title": "样例章节",
            "question": "样例问题？",
            "options": ["A", "B", "C", "D"],
            "answer": "A",
            "explanation": "样例解析",
        }
    ]
    dsl = build_classroom_dsl(stage_id="contract-test-stage", outline=outline, quizzes=quizzes)

    missing = DSL_TOP_KEYS - set(dsl.keys())
    assert not missing, f"本地 DSL 顶层缺字段（与引擎 schema 不同构）: {missing}"
    missing = STAGE_KEYS - set(dsl["stage"].keys())
    assert not missing, f"本地 DSL stage 缺字段: {missing}"
    for scene in dsl["scenes"]:
        missing = SCENE_KEYS - set(scene.keys())
        assert not missing, f"本地 scene 缺字段（scene.title={scene.get('title', '?')}）: {missing}"
    assert dsl["scenesCount"] == len(dsl["scenes"])


# ── 后端调用方锚点（防止主系统侧悄悄扩耦合面） ──────────────────────────


def test_backend_only_talks_to_engine_via_two_endpoints():
    """主系统对引擎的调用必须收敛在两个端点（防腐层纪律）。

    新增直连引擎其他 30+ 个上游 API 的代码会放大耦合面，违反
    VENDORED.md 第 2 节的边界约定——需先更新契约档案再扩面。
    """
    svc = (BACKEND_ROOT / "app" / "services" / "classroom_service.py").read_text(encoding="utf-8")
    occurrences = [ln for ln in svc.splitlines() if "/api/generate-classroom" in ln]
    assert occurrences, "classroom_service 不再调用引擎端点？"
    bad = [ln for ln in svc.splitlines() if "classroom_base_url" in ln and "/api/" in ln and "/api/generate-classroom" not in ln]
    assert not bad, f"主系统试图直连引擎非契约端点（扩耦合面）: {bad}"
