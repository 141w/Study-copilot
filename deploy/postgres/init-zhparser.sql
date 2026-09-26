-- zhparser 中文全文检索初始化（幂等，由 docker-entrypoint-initdb.d 执行）
--
-- 项目 PgVectorStore._get_fts_config 探测 pg_ts_config 中名为 'zh' 的配置；
-- 本脚本创建 zhparser 扩展并建立该配置。已有数据卷的环境需手工执行一次：
--   docker compose exec db psql -U study_user -d study_copilot -f /path/init-zhparser.sql

CREATE EXTENSION IF NOT EXISTS zhparser;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_ts_config WHERE cfgname = 'zh') THEN
        CREATE TEXT SEARCH CONFIGURATION zh (PARSER = zhparser);
        -- n=名词 v=动词 a=形容词 i=成语 e=感叹词 l=习用语 j=简称
        ALTER TEXT SEARCH CONFIGURATION zh ADD MAPPING FOR n,v,a,i,e,l,j WITH simple;
        RAISE NOTICE 'zh text search configuration created (zhparser)';
    END IF;
END
$$;
