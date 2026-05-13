#!/usr/bin/env python3
# 修复脚本

import sys

input_file = "app/core/rag_engine.py"
output_file = "app/core/rag_engine_fixed.py"

with open(input_file, "r", encoding="utf-8") as f:
    content = f.read()

# 修复中文引号
content = content.replace('"', '"').replace('"', '"')
content = content.replace(''', "'").replace(''', "'")

# 修复额外的括号
content = content.replace('int(m))', 'int(m))')
content = content.replace('list(indices))', 'list(indices))')

# 写入固定文件
with open(output_file, "w", encoding="utf-8") as f:
    f.write(content)

print(f"Fixed file written to {output_file}")
print("Please check and replace the original file")