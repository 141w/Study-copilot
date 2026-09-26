# 自定义 PostgreSQL 镜像：pgvector + zhparser（中文全文检索）
#
# 基础镜像 pgvector/pgvector:pg16 自带 pgvector；本文件追加 zhparser：
# - scws（C 分词引擎）从源码编译安装到 /usr/local
#   （git 版无 autotools configure，手工编译 libscws + 生成 version.h，
#   构建步骤已在本地 macOS 环境验证：分词输出正确）
# - zhparser 经 PGXS 安装（含词典 dict.utf8.xdb -> tsearch_data）
#
# 为什么需要：项目 hybrid 检索 = pgvector 向量 + PostgreSQL 全文 + RRF。
# 中文全文依赖 zhparser 解析器；缺失时 _get_fts_config 降级 'simple'，
# 中文整句成为一个 token，全文通道失效、hybrid 顶部召回塌方
# （评测实测 mmarco R@1 0.655 -> 0.035），且结果不可复现。
FROM pgvector/pgvector:pg16

RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        build-essential ca-certificates git postgresql-server-dev-16; \
    # 1) scws 手工编译（git 版无 configure，version.h 由模板生成）
    git clone --depth 1 https://github.com/hightman/scws.git /tmp/scws; \
    cd /tmp/scws/libscws; \
    sed -e 's/@VERSION@/1.2.3/g' -e 's/@PACKAGE_BUGREPORT@//g' version.h.in > version.h; \
    gcc -O2 -fPIC -c *.c && ar rcs libscws.a *.o; \
    mkdir -p /usr/local/include/scws /usr/local/lib; \
    cp *.h /usr/local/include/scws/ && cp libscws.a /usr/local/lib/; \
    # 2) zhparser 构建安装（GNU ld 的 -L 全局生效，无需 SCWS_LIBS 覆盖）
    git clone --depth 1 https://github.com/amutu/zhparser.git /tmp/zhparser; \
    cd /tmp/zhparser; \
    make SCWS_HOME=/usr/local PG_CONFIG="$(command -v pg_config || echo /usr/lib/postgresql/16/bin/pg_config)"; \
    make install SCWS_HOME=/usr/local PG_CONFIG="$(command -v pg_config || echo /usr/lib/postgresql/16/bin/pg_config)"; \
    # 3) 清理构建依赖
    cd /; rm -rf /tmp/scws /tmp/zhparser; \
    apt-get purge -y build-essential git postgresql-server-dev-16; \
    apt-get autoremove -y; \
    rm -rf /var/lib/apt/lists/*

# 首次初始化（空数据目录）时创建扩展与 zh 全文配置；幂等
COPY init-zhparser.sql /docker-entrypoint-initdb.d/10-zhparser.sql
